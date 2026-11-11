"""Usage rollup: pure aggregation unit tests + the HTTP endpoint over real rows."""

import uuid
from datetime import UTC, datetime, timedelta

from app.domains.credits.application.dtos import UsageRow
from app.domains.credits.application.queries import aggregate_rows, period_window
from app.domains.credits.domain import (
    CreditAction,
    CreditReservation,
    ReservationStatus,
)
from tests.helpers import create_org, register_and_login


def _row(
    *,
    user_id=None,
    email=None,
    api_key_id=None,
    key_name=None,
    action=CreditAction.LLM_CALL,
    count=1,
    credits=1,
) -> UsageRow:
    return UsageRow(
        user_id=user_id,
        user_email=email,
        user_name=None,
        api_key_id=api_key_id,
        api_key_name=key_name,
        action=action,
        count=count,
        credits=credits,
    )


def test_aggregate_rows_groups_actions_per_actor_and_orders_by_credits():
    alice, bob = uuid.uuid4(), uuid.uuid4()
    rows = [
        _row(user_id=alice, email="a@x.com", action=CreditAction.LLM_CALL, count=3, credits=3),
        _row(
            user_id=alice,
            email="a@x.com",
            action=CreditAction.IMAGE_NANO_BANANA,
            count=1,
            credits=2,
        ),
        _row(user_id=bob, email="b@x.com", action=CreditAction.LLM_CALL, count=10, credits=10),
    ]
    actors, total = aggregate_rows(rows, limits={alice: 50})

    assert total == 15
    assert [a.user_email for a in actors] == ["b@x.com", "a@x.com"]  # credits desc
    a = actors[1]
    assert a.credits == 5 and a.count == 4
    assert a.limit == 50
    assert [x.action for x in a.actions] == [
        CreditAction.LLM_CALL,
        CreditAction.IMAGE_NANO_BANANA,
    ]
    assert actors[0].limit is None


def test_aggregate_rows_handles_api_key_and_null_actor():
    key = uuid.uuid4()
    rows = [
        _row(api_key_id=key, key_name="Zapier", credits=4, count=4),
        _row(),  # deleted user AND no key: all-null actor group
    ]
    actors, total = aggregate_rows(rows, limits={})
    assert total == 5
    assert actors[0].api_key_name == "Zapier"
    assert actors[0].limit is None  # keys never have member limits
    assert actors[1].user_id is None and actors[1].api_key_id is None


def test_period_window_handles_year_rollover():
    start, end = period_window("2026-12")
    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


# -- HTTP endpoint over persisted reservations ---------------------------------


async def _seed_reservation(
    db,
    *,
    org_id: str,
    user_id: str | None = None,
    status: ReservationStatus = ReservationStatus.CAPTURED,
    action: CreditAction = CreditAction.LLM_CALL,
    amount: int = 1,
    created_at: datetime | None = None,
) -> None:
    reservation = CreditReservation(
        organization_id=uuid.UUID(org_id),
        user_id=uuid.UUID(user_id) if user_id else None,
        action=action,
        amount=amount,
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    if created_at is not None:
        reservation.created_at = created_at
    db.add(reservation)
    await db.commit()


async def test_usage_endpoint_groups_and_excludes_correctly(client, db):
    owner, headers = await register_and_login(client, "usage-owner@example.com")
    org = await create_org(client, headers)
    org_id = org["id"]
    other, _ = await register_and_login(client, "usage-member@example.com")

    now = datetime.now(UTC)
    # Counted: captured this month.
    await _seed_reservation(db, org_id=org_id, user_id=owner["id"], amount=3)
    await _seed_reservation(
        db, org_id=org_id, user_id=owner["id"], action=CreditAction.IMAGE_NANO_BANANA, amount=2
    )
    await _seed_reservation(db, org_id=org_id, user_id=other["id"], amount=1)
    # Excluded: pending, released, and prior-month captured.
    await _seed_reservation(
        db, org_id=org_id, user_id=owner["id"], status=ReservationStatus.PENDING
    )
    await _seed_reservation(
        db, org_id=org_id, user_id=owner["id"], status=ReservationStatus.RELEASED
    )
    await _seed_reservation(
        db, org_id=org_id, user_id=owner["id"], amount=99, created_at=now - timedelta(days=40)
    )

    res = await client.get(f"/api/orgs/{org_id}/credits/usage", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["period"] == now.strftime("%Y-%m")
    assert body["total_credits"] == 6
    assert body["total_actors"] == 2
    top = body["items"][0]
    assert top["user_email"] == "usage-owner@example.com"
    assert top["credits"] == 5 and top["count"] == 2
    assert {a["action"] for a in top["actions"]} == {"llm_call", "image_nano_banana"}
    assert body["items"][1]["credits"] == 1


async def test_usage_endpoint_includes_member_limit(client, db):
    owner, headers = await register_and_login(client, "usage-limit@example.com")
    org = await create_org(client, headers)
    org_id = org["id"]

    await _seed_reservation(db, org_id=org_id, user_id=owner["id"], amount=4)
    res = await client.put(
        f"/api/orgs/{org_id}/credits/member-limits/{owner['id']}",
        json={"monthly_limit": 20},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    res = await client.get(f"/api/orgs/{org_id}/credits/usage", headers=headers)
    body = res.json()
    assert body["items"][0]["limit"] == 20


async def test_usage_endpoint_null_actor_and_empty_period(client, db):
    _, headers = await register_and_login(client, "usage-null@example.com")
    org = await create_org(client, headers)
    org_id = org["id"]

    # A captured row whose user was deleted (user_id already NULL).
    await _seed_reservation(db, org_id=org_id, user_id=None, amount=2)

    res = await client.get(f"/api/orgs/{org_id}/credits/usage", headers=headers)
    body = res.json()
    assert body["total_actors"] == 1
    row = body["items"][0]
    assert row["user_id"] is None and row["api_key_id"] is None
    assert row["user_email"] is None

    # A period with no usage is an empty page, not an error.
    res = await client.get(
        f"/api/orgs/{org_id}/credits/usage", params={"period": "2020-01"}, headers=headers
    )
    body = res.json()
    assert body["items"] == [] and body["total_credits"] == 0


async def test_usage_endpoint_validation_and_tenancy(client, db):
    _, headers = await register_and_login(client, "usage-guard@example.com")
    org = await create_org(client, headers)

    res = await client.get(
        f"/api/orgs/{org['id']}/credits/usage", params={"period": "2026-13"}, headers=headers
    )
    assert res.status_code == 422

    _, outsider = await register_and_login(client, "usage-outsider@example.com")
    res = await client.get(f"/api/orgs/{org['id']}/credits/usage", headers=outsider)
    assert res.status_code == 404
