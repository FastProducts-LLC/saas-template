"""Entitlement HTTP contracts using real plan, override, and usage persistence."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.domains.audit.domain import AuditEvent, actions
from app.domains.billing.domain import BillingInterval, Plan, PlanSubscriptionStatus, Subscription
from app.domains.entitlements.domain import (
    PLAN_ENTITLEMENTS,
    EntitlementKey,
    EntitlementOverride,
    EntitlementRequired,
)
from app.domains.entitlements.interface.deps import build_entitlement_service, require_entitlement
from app.domains.organizations.domain import Invitation, Membership, Role
from tests.helpers import create_org, make_superuser, register_and_login


async def entitlement_context(client, db, *, admin=False, email="owner@gmail.com"):
    user, headers = await register_and_login(client, email)
    org = await create_org(client, headers)
    if admin:
        await make_superuser(db, user["id"])
    return SimpleNamespace(
        user_id=uuid.UUID(user["id"]),
        org_id=uuid.UUID(org["id"]),
        headers=headers,
        path=f"/api/orgs/{org['id']}",
        admin_path=f"/api/admin/organizations/{org['id']}/entitlements",
    )


@pytest_asyncio.fixture
async def ctx(client, db):
    return await entitlement_context(client, db, admin=True)


async def paid_plan(db, org_id, plan=Plan.PRO):
    db.add(
        Subscription(
            organization_id=org_id,
            stripe_subscription_id=f"sub_{org_id}",
            plan=plan,
            interval=BillingInterval.MONTHLY,
            status=PlanSubscriptionStatus.ACTIVE,
            current_period_end=datetime.now(UTC) + timedelta(days=30),
        )
    )
    await db.commit()


async def snapshot(client, ctx):
    response = await client.get(ctx.path + "/entitlements", headers=ctx.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    return body, {row["key"]: row for row in body["entitlements"]}


async def put_override(client, ctx, key="seats", **values):
    return await client.put(ctx.admin_path + f"/{key}", headers=ctx.headers, json=values)


async def audit_rows(db, ctx, action):
    return list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.organization_id == ctx.org_id,
                    AuditEvent.action == action,
                )
                .order_by(AuditEvent.created_at)
            )
        ).all()
    )


async def test_snapshot_free_plan_defaults(client, ctx):
    body, entries = await snapshot(client, ctx)
    assert body["plan"] == Plan.FREE.value
    assert len(entries) == len(body["entitlements"]) == len(EntitlementKey)
    for key in EntitlementKey:
        assert entries[key.value] == {
            "key": key.value,
            "limit": PLAN_ENTITLEMENTS[Plan.FREE][key],
            "used": 1 if key == EntitlementKey.SEATS else 0,
            "included": True,
            "source": "plan",
            "expires_at": None,
        }


@pytest.mark.parametrize("plan", [Plan.PRO, Plan.TEAM])
async def test_snapshot_reflects_paid_plan(client, db, ctx, plan):
    await paid_plan(db, ctx.org_id, plan)
    body, entries = await snapshot(client, ctx)
    assert body["plan"] == plan.value
    for key in EntitlementKey:
        assert entries[key.value]["limit"] == PLAN_ENTITLEMENTS[plan][key]


async def test_snapshot_reports_usage_counts(client, db, ctx):
    for index in range(2):
        response = await client.post(
            ctx.path + "/api-keys",
            headers=ctx.headers,
            json={"name": f"key-{index}"},
        )
        assert response.status_code == 201, response.text
    response = await client.delete(
        ctx.path + f"/api-keys/{response.json()['id']}",
        headers=ctx.headers,
    )
    assert response.status_code == 204
    now = datetime.now(UTC)
    for index, (expires, accepted) in enumerate(
        [
            (now + timedelta(days=1), None),
            (now - timedelta(days=1), None),
            (now + timedelta(days=1), now),
        ]
    ):
        db.add(
            Invitation(
                organization_id=ctx.org_id,
                email=f"invite-{index}@example.net",
                role=Role.MEMBER,
                token_hash=f"usage-{index}",
                expires_at=expires,
                accepted_at=accepted,
            )
        )
    await db.commit()
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 2
    assert entries["api_keys"]["used"] == 1


async def test_snapshot_requires_membership(client, ctx):
    _, outsider = await register_and_login(client, "outsider@yahoo.com")
    response = await client.get(ctx.path + "/entitlements", headers=outsider)
    assert response.status_code == 404
    assert (await client.get(ctx.path + "/entitlements")).status_code == 401


async def test_admin_set_override_changes_limit_and_audits(client, db, ctx):
    expiry = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    response = await put_override(client, ctx, limit_value=12, note="Support", expires_at=expiry)
    assert response.status_code == 200, response.text
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["limit"] == 12
    assert entries["seats"]["source"] == "override"
    assert datetime.fromisoformat(entries["seats"]["expires_at"]) == datetime.fromisoformat(expiry)
    events = await audit_rows(db, ctx, actions.ENTITLEMENT_OVERRIDE_SET)
    assert len(events) == 1
    assert events[0].actor_user_id == ctx.user_id
    assert events[0].meta == {"key": "seats", "old_limit": None, "new_limit": 12}
    response = await client.get(ctx.admin_path, headers=ctx.headers)
    assert response.status_code == 200, response.text
    raw = response.json()["overrides"]
    assert len(raw) == 1
    assert raw[0]["created_by_id"] == str(ctx.user_id)
    assert raw[0]["note"] == "Support"
    assert raw[0]["updated_at"]
    assert raw[0]["key"] == "seats"
    assert raw[0]["limit_value"] == 12


async def test_admin_override_null_means_unlimited(client, ctx):
    response = await put_override(client, ctx, limit_value=None)
    assert response.status_code == 200, response.text
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["limit"] is None
    assert entries["seats"]["included"] is True
    assert entries["seats"]["source"] == "override"


async def test_admin_override_expired_falls_back_to_plan(client, db, ctx):
    db.add(
        EntitlementOverride(
            organization_id=ctx.org_id,
            key=EntitlementKey.SEATS,
            limit_value=99,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    await db.commit()
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["limit"] == PLAN_ENTITLEMENTS[Plan.FREE][EntitlementKey.SEATS]
    assert entries["seats"]["source"] == "plan"
    assert entries["seats"]["expires_at"] is None
    response = await client.get(ctx.admin_path, headers=ctx.headers)
    assert response.json()["overrides"][0]["limit_value"] == 99


async def test_admin_override_upsert_keeps_one_row(client, db, ctx):
    for limit in (9, 14):
        response = await put_override(client, ctx, limit_value=limit)
        assert response.status_code == 200, response.text
    assert (
        await db.scalar(
            select(func.count())
            .select_from(EntitlementOverride)
            .where(
                EntitlementOverride.organization_id == ctx.org_id,
                EntitlementOverride.key == EntitlementKey.SEATS,
            )
        )
        == 1
    )
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["limit"] == 14
    events = await audit_rows(db, ctx, actions.ENTITLEMENT_OVERRIDE_SET)
    assert len(events) == 2
    assert events[-1].meta == {"key": "seats", "old_limit": 9, "new_limit": 14}


async def test_admin_delete_override_restores_plan_default(client, db, ctx):
    assert (await put_override(client, ctx, limit_value=10)).status_code == 200
    response = await client.delete(ctx.admin_path + "/seats", headers=ctx.headers)
    assert response.status_code == 204, response.text
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["limit"] == PLAN_ENTITLEMENTS[Plan.FREE][EntitlementKey.SEATS]
    assert entries["seats"]["source"] == "plan"
    events = await audit_rows(db, ctx, actions.ENTITLEMENT_OVERRIDE_REMOVED)
    assert len(events) == 1
    assert events[0].actor_user_id == ctx.user_id
    assert events[0].meta == {"key": "seats", "old_limit": 10}
    assert (await client.get(ctx.admin_path, headers=ctx.headers)).json()["overrides"] == []


async def test_admin_delete_missing_override_is_204_without_audit(client, db, ctx):
    response = await client.delete(ctx.admin_path + "/seats", headers=ctx.headers)
    assert response.status_code == 204, response.text
    assert await audit_rows(db, ctx, actions.ENTITLEMENT_OVERRIDE_REMOVED) == []


@pytest.mark.parametrize("method", ["put", "delete"])
async def test_admin_override_unknown_key_is_422(client, ctx, method):
    kwargs = {"json": {"limit_value": 3}} if method == "put" else {}
    response = await client.request(
        method,
        ctx.admin_path + "/unknown",
        headers=ctx.headers,
        **kwargs,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "ERR_ENT_003"


async def test_admin_override_negative_limit_is_422(client, ctx):
    assert (await put_override(client, ctx, limit_value=-1)).status_code == 422


@pytest.mark.parametrize(
    "expiry",
    [
        "2000-01-01T00:00:00+00:00",
        "2099-01-01T00:00:00",
    ],
)
async def test_admin_override_past_expiry_is_422(client, ctx, expiry):
    assert (await put_override(client, ctx, limit_value=5, expires_at=expiry)).status_code == 422


@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_admin_override_unknown_org_is_404(client, ctx, method):
    path = f"/api/admin/organizations/{uuid.uuid4()}/entitlements"
    if method != "get":
        path += "/seats"
    kwargs = {"json": {"limit_value": 3}} if method == "put" else {}
    response = await client.request(method, path, headers=ctx.headers, **kwargs)
    assert response.status_code == 404
    assert response.json()["code"] == "ERR_PERM_002"


@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_admin_endpoints_require_superuser(client, ctx, method):
    _, headers = await register_and_login(client, "regular@yahoo.com")
    path = ctx.admin_path + ("/seats" if method != "get" else "")
    kwargs = {"json": {"limit_value": 3}} if method == "put" else {}
    response = await client.request(method, path, headers=headers, **kwargs)
    assert response.status_code == 403
    assert response.json()["code"] == "ERR_PERM_004"


async def test_ensure_included_blocks_when_limit_zero(client, db, ctx):
    response = await put_override(client, ctx, limit_value=0)
    assert response.status_code == 200, response.text
    service = build_entitlement_service(db)
    with pytest.raises(EntitlementRequired):
        await service.ensure_included(ctx.org_id, EntitlementKey.SEATS)
    membership = await db.scalar(
        select(Membership).where(
            Membership.organization_id == ctx.org_id,
            Membership.user_id == ctx.user_id,
        )
    )
    with pytest.raises(EntitlementRequired):
        await require_entitlement(EntitlementKey.SEATS).dependency(membership, db)
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["included"] is False


@pytest.mark.parametrize("payload", [{}, {"limit_value": 1, "note": "x" * 501}])
async def test_admin_override_validates_required_limit_and_note(client, ctx, payload):
    assert (await put_override(client, ctx, **payload)).status_code == 422
