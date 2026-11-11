"""Server-side seat/key gates, tenant isolation, and transaction serialization."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.domains.auth.domain import User
from app.domains.billing.domain import Plan
from app.domains.entitlements.application.use_cases import EntitlementService
from app.domains.entitlements.domain import (
    PLAN_ENTITLEMENTS,
    EntitlementKey,
    EntitlementLimitReached,
    EntitlementOverride,
)
from app.domains.organizations.domain import Invitation, Membership, Organization
from app.domains.organizations.interface import deps as org_deps
from tests.helpers import make_superuser, register_and_login, verify_email
from tests.test_entitlements_api import entitlement_context, paid_plan, put_override, snapshot


@pytest_asyncio.fixture
async def ctx(client, db, monkeypatch):
    context = await entitlement_context(client, db)
    context.tokens = {}

    async def capture(invitation, org, inviter, raw_token):
        context.tokens[invitation.email] = raw_token

    # Keep the production factory and entitlement gate, replace only email delivery.
    monkeypatch.setattr(org_deps._notifier, "send_invitation", capture)
    return context


async def invite(client, ctx, index=0):
    return await client.post(
        ctx.path + "/invitations",
        headers=ctx.headers,
        json={"email": f"invite-{index}@example.net", "role": "member"},
    )


async def pending_seats(client, ctx, count=4):
    rows = []
    for index in range(count):
        response = await invite(client, ctx, index)
        assert response.status_code == 201, response.text
        rows.append(response.json())
    return rows


async def active_members(db, ctx, count=4):
    for index in range(count):
        user = User(
            email=f"active-{index}@example.net",
            password_hash="unused",
            first_name="Member",
        )
        db.add(user)
        await db.flush()
        db.add(Membership(organization_id=ctx.org_id, user_id=user.id))
    await db.commit()


async def create_key(client, ctx):
    return await client.post(ctx.path + "/api-keys", headers=ctx.headers, json={"name": "Test"})


async def fill_keys(client, ctx, count=5):
    rows = []
    for _ in range(count):
        response = await create_key(client, ctx)
        assert response.status_code == 201, response.text
        rows.append(response.json())
    return rows


async def test_invite_allowed_below_seat_limit(client, ctx):
    response = await invite(client, ctx)
    assert response.status_code == 201, response.text
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 2


async def test_invite_refused_at_seat_limit(client, db, ctx):
    await active_members(db, ctx)
    response = await invite(client, ctx)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "ERR_ENT_002"
    # Clients render "…plan limit of 5 seats." from these.
    assert response.json()["params"] == {"limit": 5, "resource": "seats"}
    assert (
        await db.scalar(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.organization_id == ctx.org_id,
            )
        )
        == 0
    )
    assert ctx.tokens == {}


async def test_pending_invitations_count_toward_seats(client, ctx):
    await pending_seats(client, ctx)
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 5
    response = await invite(client, ctx, 5)
    assert response.status_code == 403, response.text
    assert len(ctx.tokens) == 4


async def test_revoked_invitation_frees_a_seat(client, ctx):
    rows = await pending_seats(client, ctx)
    assert (await invite(client, ctx, 5)).status_code == 403
    response = await client.delete(
        ctx.path + f"/invitations/{rows[0]['id']}",
        headers=ctx.headers,
    )
    assert response.status_code == 204, response.text
    assert (await invite(client, ctx, 5)).status_code == 201
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 5


async def test_accepting_invitation_at_limit_still_works(client, ctx):
    await pending_seats(client, ctx)
    _, headers = await register_and_login(client, "invite-0@example.net")
    response = await client.post(
        "/api/invitations/accept",
        headers=headers,
        json={"token": ctx.tokens["invite-0@example.net"]},
    )
    assert response.status_code == 200, response.text
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 5
    response = await client.get(ctx.path + "/members", headers=ctx.headers)
    assert len(response.json()) == 2
    assert (await invite(client, ctx, 5)).status_code == 403


async def test_auto_join_skipped_when_org_full(client, db, ctx):
    org = await db.get(Organization, ctx.org_id)
    org.email_domain = "auto-entitlements.com"
    await active_members(db, ctx)
    user, headers = await register_and_login(
        client,
        "new@auto-entitlements.com",
        verified=False,
    )
    await verify_email(client, user["id"])
    response = await client.get("/api/orgs", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == []
    saved_user = await db.get(User, uuid.UUID(user["id"]))
    assert saved_user.email_verified
    assert (
        await db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == ctx.org_id,
            )
        )
        == 5
    )


async def test_paid_plan_raises_seat_limit(client, db, ctx):
    await pending_seats(client, ctx)
    assert (await invite(client, ctx, 5)).status_code == 403
    await paid_plan(db, ctx.org_id)
    assert (await invite(client, ctx, 5)).status_code == 201
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["limit"] == PLAN_ENTITLEMENTS[Plan.PRO][EntitlementKey.SEATS]
    assert entries["seats"]["used"] == 6


async def test_api_key_refused_at_limit(client, ctx):
    await fill_keys(client, ctx)
    response = await create_key(client, ctx)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "ERR_ENT_002"
    response = await client.get(ctx.path + "/api-keys", headers=ctx.headers)
    assert len(response.json()) == 5


async def test_revoked_api_keys_do_not_count(client, ctx):
    keys = await fill_keys(client, ctx)
    assert (await create_key(client, ctx)).status_code == 403
    response = await client.delete(ctx.path + f"/api-keys/{keys[0]['id']}", headers=ctx.headers)
    assert response.status_code == 204, response.text
    assert (await create_key(client, ctx)).status_code == 201
    _, entries = await snapshot(client, ctx)
    assert entries["api_keys"]["used"] == 5


async def test_override_raises_api_key_limit(client, db, ctx):
    await fill_keys(client, ctx)
    assert (await create_key(client, ctx)).status_code == 403
    await make_superuser(db, ctx.user_id)
    response = await put_override(client, ctx, "api_keys", limit_value=6)
    assert response.status_code == 200, response.text
    assert (await create_key(client, ctx)).status_code == 201
    assert (await create_key(client, ctx)).status_code == 403


async def test_limit_error_is_catalogued_403(client, ctx):
    await fill_keys(client, ctx)
    response = await create_key(client, ctx)
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == EntitlementLimitReached.internal_code == "ERR_ENT_002"
    assert body["status"] == 403
    assert body["instance"]


async def test_gate_lock_is_taken_before_count():
    events = []
    org_id = uuid.uuid4()
    key = EntitlementKey.SEATS

    async def acquire(actual_org, actual_key):
        assert (actual_org, actual_key) == (org_id, key)
        events.append("lock")

    async def count():
        events.append("count")
        return PLAN_ENTITLEMENTS[Plan.FREE][key]

    service = EntitlementService(
        SimpleNamespace(get=AsyncMock(return_value=None)),
        SimpleNamespace(plan_for=AsyncMock(return_value=Plan.FREE)),
        SimpleNamespace(acquire=acquire),
    )
    with pytest.raises(EntitlementLimitReached):
        await service.ensure_within_limit(org_id, key, count)
    assert events == ["lock", "count"]


async def test_other_orgs_usage_does_not_count(client, db, ctx):
    await pending_seats(client, ctx)
    await fill_keys(client, ctx)
    other = await entitlement_context(client, db, email="other@yahoo.com")
    _, entries = await snapshot(client, other)
    assert entries["seats"]["used"] == 1
    assert entries["api_keys"]["used"] == 0
    assert (await invite(client, other, 9)).status_code == 201
    assert (await create_key(client, other)).status_code == 201
    _, entries = await snapshot(client, other)
    assert entries["seats"]["used"] == 2
    assert entries["api_keys"]["used"] == 1
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == entries["api_keys"]["used"] == 5


@pytest.mark.parametrize("plan", [Plan.FREE, Plan.TEAM])
async def test_unlimited_skips_lock_and_count(plan):
    org_id = uuid.uuid4()
    override = (
        EntitlementOverride(org_id, EntitlementKey.SEATS, None) if plan == Plan.FREE else None
    )
    locks = SimpleNamespace(acquire=AsyncMock())
    count = AsyncMock(return_value=100)
    service = EntitlementService(
        SimpleNamespace(get=AsyncMock(return_value=override)),
        SimpleNamespace(plan_for=AsyncMock(return_value=plan)),
        locks,
    )
    await service.ensure_within_limit(org_id, EntitlementKey.SEATS, count)
    locks.acquire.assert_not_called()
    count.assert_not_called()


async def test_expired_invitations_do_not_reserve_seats(client, db, ctx):
    rows = await pending_seats(client, ctx)
    row = await db.get(Invitation, uuid.UUID(rows[0]["id"]))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    assert (await invite(client, ctx, 5)).status_code == 201
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 5


async def test_concurrent_api_key_requests_share_last_slot(client, ctx):
    await fill_keys(client, ctx, count=4)
    responses = await asyncio.gather(create_key(client, ctx), create_key(client, ctx))
    assert sorted(response.status_code for response in responses) == [201, 403]
    _, entries = await snapshot(client, ctx)
    assert entries["api_keys"]["used"] == 5


async def test_concurrent_invitations_share_last_seat(client, ctx):
    await pending_seats(client, ctx, count=3)
    responses = await asyncio.gather(invite(client, ctx, 8), invite(client, ctx, 9))
    assert sorted(response.status_code for response in responses) == [201, 403]
    _, entries = await snapshot(client, ctx)
    assert entries["seats"]["used"] == 5
