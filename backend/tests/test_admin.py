"""Admin API tests: superuser-only platform endpoints.

Access control note: the superuser gate is DB-read per request — `get_current_user`
reloads the User from the database on every call and `get_current_superuser` reads
`is_superuser` off that fresh entity. So flipping the flag with `make_superuser`
takes effect immediately; the already-issued access token does NOT need re-minting.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.domains.admin.domain import AdminAuditEntry
from app.domains.api_keys.domain import ApiKey
from app.domains.auth.domain import User
from app.domains.billing.domain import BillingAccount
from app.domains.credits.domain import (
    CreditAction,
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    MemberCreditLimit,
    ReservationStatus,
    TransactionType,
)
from app.domains.generations.domain import Generation, GenerationStatus
from app.domains.llm.domain import LlmCall, LlmProvider
from app.domains.organizations.domain import Invitation, Membership, Organization, Role
from tests.helpers import (
    create_org,
    make_superuser,
    register_and_login,
)


async def _superuser(client, db, email: str = "admin@example.com") -> tuple[dict, dict]:
    """Register, login, promote to superuser, and return (user_body, headers).

    The pre-promotion token keeps working because the superuser check reads the
    DB per request — no re-login required.
    """
    user, headers = await register_and_login(client, email)
    await make_superuser(db, user["id"])
    return user, headers


# ── Access control ────────────────────────────────────────────────────

# (method, path) for every admin route — a non-superuser must be rejected
# before any handler logic runs, so unknown ids here are fine.
_FAKE = "00000000-0000-0000-0000-000000000000"
ADMIN_ENDPOINTS = [
    ("GET", "/api/admin/stats"),
    ("GET", "/api/admin/analytics"),
    ("GET", "/api/admin/organizations"),
    ("GET", "/api/admin/customers"),
    ("POST", f"/api/admin/organizations/{_FAKE}/suspend"),
    ("POST", f"/api/admin/organizations/{_FAKE}/unsuspend"),
    ("GET", f"/api/admin/organizations/{_FAKE}/members"),
    ("POST", f"/api/admin/organizations/{_FAKE}/credits/adjust"),
    ("GET", "/api/admin/users"),
    ("POST", f"/api/admin/users/{_FAKE}/deactivate"),
    ("POST", f"/api/admin/users/{_FAKE}/reactivate"),
    ("POST", f"/api/admin/users/{_FAKE}/signout-everywhere"),
    ("POST", f"/api/admin/users/{_FAKE}/impersonate"),
    ("GET", "/api/admin/credits"),
    ("GET", "/api/admin/generations"),
    ("GET", "/api/admin/invitations"),
    ("DELETE", f"/api/admin/invitations/{_FAKE}"),
    ("GET", "/api/admin/audit-log"),
    ("GET", f"/api/admin/errors/{_FAKE}"),
    ("GET", "/api/admin/privacy-requests"),
    ("GET", f"/api/admin/privacy-requests/{_FAKE}"),
    ("POST", f"/api/admin/privacy-requests/{_FAKE}/verify"),
]


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
async def test_non_superuser_is_forbidden(client, method, path):
    _, headers = await register_and_login(client)
    res = await client.request(method, path, headers=headers, json={})
    assert res.status_code == 403, f"{method} {path} -> {res.status_code}: {res.text}"
    assert res.json()["code"] == "ERR_PERM_004", res.text


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
async def test_unauthenticated_is_unauthorized(client, method, path):
    res = await client.request(method, path, json={})
    assert res.status_code == 401, f"{method} {path} -> {res.status_code}: {res.text}"


async def test_superuser_can_reach_admin_with_existing_token(client, db):
    # Proves DB-read propagation: promote AFTER login, reuse the same token.
    _, headers = await _superuser(client, db)
    res = await client.get("/api/admin/stats", headers=headers)
    assert res.status_code == 200, res.text


# ── Stats ─────────────────────────────────────────────────────────────


async def test_stats_returns_platform_counts(client, db):
    # Seed: one admin + one regular user, and one org owned by the admin.
    admin, headers = await _superuser(client, db)
    await register_and_login(client, "member@example.com")
    await create_org(client, headers, name="Acme")

    res = await client.get("/api/admin/stats", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_users"] == 2
    assert body["active_users"] == 2
    assert body["total_organizations"] == 1


async def test_analytics_returns_dashboard_shape(client, db):
    _, headers = await _superuser(client, db)
    await create_org(client, headers, name="Acme")

    res = await client.get("/api/admin/analytics", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert {
        "user_signups",
        "org_signups",
        "credits_spent_daily",
        "generations_by_status",
        "generations_by_kind",
        "top_customers_by_credits",
        "credit_summary",
        "commercial_summary",
        "operations_summary",
        "security_summary",
        "recent_admin_actions",
    } <= body.keys()
    # 30-day zero-filled series, today included.
    assert len(body["user_signups"]) >= 30
    assert body["user_signups"][-1]["count"] >= 1
    assert body["credit_summary"]["total_balance"] == 0
    assert body["commercial_summary"]["organizations_with_wallet"] == 0
    assert body["operations_summary"]["open_privacy_requests"] == 0
    assert body["security_summary"]["superusers"] >= 1


# ── Users listing ─────────────────────────────────────────────────────


async def test_list_users_returns_paginated_shape(client, db):
    _, headers = await _superuser(client, db)
    await register_and_login(client, "member@example.com")

    res = await client.get("/api/admin/users", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert len(body["items"]) == 2
    item = body["items"][0]
    assert {"id", "email", "name", "is_active", "is_superuser", "organization_count"} <= item.keys()


async def test_list_users_pagination_limits_page_size(client, db):
    _, headers = await _superuser(client, db)
    await register_and_login(client, "member@example.com")

    res = await client.get("/api/admin/users", params={"page_size": 1, "page": 1}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    assert body["page_size"] == 1
    assert len(body["items"]) == 1

    res2 = await client.get("/api/admin/users", params={"page_size": 1, "page": 2}, headers=headers)
    assert len(res2.json()["items"]) == 1
    # Different page yields a different user.
    assert res.json()["items"][0]["id"] != res2.json()["items"][0]["id"]


async def test_list_users_search_by_email(client, db):
    _, headers = await _superuser(client, db)
    await register_and_login(client, "findme@example.com")

    res = await client.get("/api/admin/users", params={"search": "findme"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "findme@example.com"


# ── Organizations listing ─────────────────────────────────────────────


async def test_list_organizations_includes_member_count(client, db):
    _, headers = await _superuser(client, db)
    await create_org(client, headers, name="Acme")

    res = await client.get("/api/admin/organizations", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    org = body["items"][0]
    assert org["name"] == "Acme"
    expected = {"id", "slug", "member_count", "suspended_at"}
    assert expected <= org.keys()
    # Creator is the sole member.
    assert org["member_count"] == 1


# ── Customers / usage ─────────────────────────────────────────────────


async def test_list_customers_includes_owner_and_zero_usage(client, db):
    admin, headers = await _superuser(client, db)
    await create_org(client, headers, name="Acme")

    res = await client.get("/api/admin/customers", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["organization_name"] == "Acme"
    assert row["owner_email"] == admin["email"]
    assert row["member_count"] == 1
    assert row["credits_spent"] == 0
    assert row["credit_balance"] is None


async def test_list_customers_aggregates_credits(client, db):
    from datetime import UTC, datetime, timedelta

    from app.domains.credits.domain import (
        CreditAction,
        CreditReservation,
        CreditWallet,
        ReservationStatus,
    )

    admin, headers = await _superuser(client, db)
    org = await create_org(client, headers, name="Busy Co")
    org_id = uuid.UUID(org["id"])
    user_id = uuid.UUID(admin["id"])

    db.add(CreditWallet(organization_id=org_id, balance=40))
    db.add(
        CreditReservation(
            organization_id=org_id,
            user_id=user_id,
            action=CreditAction.LLM_CALL,
            amount=1,
            status=ReservationStatus.CAPTURED,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    db.add(
        CreditReservation(
            organization_id=org_id,
            user_id=user_id,
            action=CreditAction.IMAGE_NANO_BANANA,
            amount=5,
            status=ReservationStatus.CAPTURED,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    # Released holds must not count toward credits_spent.
    db.add(
        CreditReservation(
            organization_id=org_id,
            user_id=user_id,
            action=CreditAction.LLM_CALL,
            amount=1,
            status=ReservationStatus.RELEASED,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    await db.commit()

    res = await client.get("/api/admin/customers", headers=headers)
    assert res.status_code == 200, res.text
    row = res.json()["items"][0]
    assert row["credits_spent"] == 6
    assert row["credit_balance"] == 40


async def test_list_customers_search_by_owner_email(client, db):
    _, headers = await _superuser(client, db, email="owner@owner-search.com")
    await create_org(client, headers, name="Acme")
    _, other_headers = await register_and_login(client, "other@other-search.com")
    await create_org(client, other_headers, name="Other Co")

    res = await client.get(
        "/api/admin/customers",
        params={"search": "owner@owner-search"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["organization_name"] == "Acme"
    assert body["items"][0]["owner_email"] == "owner@owner-search.com"


# ── Organization members ──────────────────────────────────────────────


async def test_list_org_members_returns_creator(client, db):
    admin, headers = await _superuser(client, db)
    org = await create_org(client, headers, name="Acme")

    res = await client.get(f"/api/admin/organizations/{org['id']}/members", headers=headers)
    assert res.status_code == 200, res.text
    members = res.json()
    assert len(members) == 1
    member = members[0]
    assert member["email"] == admin["email"]
    assert {"user_id", "role", "is_active", "joined_at"} <= member.keys()


async def test_list_org_members_unknown_org_404(client, db):
    _, headers = await _superuser(client, db)
    res = await client.get(f"/api/admin/organizations/{uuid.uuid4()}/members", headers=headers)
    assert res.status_code == 404, res.text
    assert res.json()["code"] == "ERR_ADM_002"


# ── Organization merge ─────────────────────────────────────────────────


async def test_merge_organizations_moves_owned_data_and_audits(client, db):
    admin, headers = await _superuser(client, db, email="admin@target-merge.com")
    target = await create_org(client, headers, name="Target Co")

    source_owner, source_headers = await register_and_login(client, "owner@source-merge.com")
    source = await create_org(client, source_headers, name="Source Co")

    member, _ = await register_and_login(client, "member@member-merge.com")

    admin_id = uuid.UUID(admin["id"])
    source_owner_id = uuid.UUID(source_owner["id"])
    member_id = uuid.UUID(member["id"])
    target_id = uuid.UUID(target["id"])
    source_id = uuid.UUID(source["id"])

    expires_at = datetime.now(UTC) + timedelta(days=7)
    source_key = ApiKey(
        organization_id=source_id,
        name="Source key",
        key_prefix="sk_source",
        key_hash="source-key-hash",
        created_by_id=source_owner_id,
    )
    source_reservation = CreditReservation(
        organization_id=source_id,
        user_id=source_owner_id,
        api_key_id=source_key.id,
        action=CreditAction.IMAGE_GPT,
        amount=5,
        status=ReservationStatus.CAPTURED,
        expires_at=expires_at,
    )

    db.add_all(
        [
            # Source has one duplicate target member and two members that should move.
            Membership(organization_id=source_id, user_id=admin_id, role=Role.MEMBER),
            Membership(organization_id=source_id, user_id=member_id, role=Role.MEMBER),
            CreditWallet(organization_id=target_id, balance=30),
            CreditWallet(organization_id=source_id, balance=20),
            source_key,
            source_reservation,
            CreditTransaction(
                organization_id=source_id,
                user_id=source_owner_id,
                api_key_id=source_key.id,
                reservation_id=source_reservation.id,
                type=TransactionType.HOLD,
                action=CreditAction.IMAGE_GPT,
                amount=-5,
                balance_after=15,
                description="Source hold",
            ),
            Generation(
                organization_id=source_id,
                user_id=source_owner_id,
                kind=CreditAction.IMAGE_GPT,
                model="gpt-image-test",
                prompt="source prompt",
                status=GenerationStatus.SUCCEEDED,
                reservation_id=source_reservation.id,
                credits_cost=5,
            ),
            LlmCall.pending(
                organization_id=source_id,
                user_id=source_owner_id,
                provider=LlmProvider.OPENAI,
                model="gpt-test",
                prompt="source prompt",
                reservation_id=source_reservation.id,
                credits_cost=1,
            ),
            Invitation(
                organization_id=source_id,
                email="pending@example.com",
                role=Role.MEMBER,
                token_hash="source-invite-token-hash",
                expires_at=expires_at,
                invited_by_id=source_owner_id,
            ),
            BillingAccount(organization_id=target_id, stripe_customer_id="cus_target"),
            BillingAccount(organization_id=source_id, stripe_customer_id="cus_source"),
            MemberCreditLimit(organization_id=target_id, user_id=admin_id, monthly_limit=10),
            # Duplicate source limit is dropped because the target already has one.
            MemberCreditLimit(organization_id=source_id, user_id=admin_id, monthly_limit=99),
            MemberCreditLimit(organization_id=source_id, user_id=member_id, monthly_limit=12),
        ]
    )
    await db.commit()

    res = await client.post(
        "/api/admin/organizations/merge",
        json={"target_id": str(target_id), "source_ids": [str(source_id)]},
        headers=headers,
    )

    assert res.status_code == 200, res.text
    assert res.json() == {
        "target_id": str(target_id),
        "merged_count": 1,
        "members_moved": 2,
    }

    db.expire_all()

    assert await db.get(Organization, source_id) is None
    target_wallet = (
        await db.execute(select(CreditWallet).where(CreditWallet.organization_id == target_id))
    ).scalar_one()
    assert target_wallet.balance == 50
    assert (
        await db.execute(select(CreditWallet).where(CreditWallet.organization_id == source_id))
    ).scalar_one_or_none() is None

    target_members = (
        (
            await db.execute(
                select(Membership.user_id).where(Membership.organization_id == target_id)
            )
        )
        .scalars()
        .all()
    )
    assert set(target_members) == {admin_id, source_owner_id, member_id}
    assert (
        await db.scalar(
            select(func.count(Membership.id)).where(Membership.organization_id == source_id)
        )
        == 0
    )

    for model in (ApiKey, CreditReservation, CreditTransaction, Generation, LlmCall, Invitation):
        assert (
            await db.scalar(select(func.count(model.id)).where(model.organization_id == target_id))
            == 1
        )
        assert (
            await db.scalar(select(func.count(model.id)).where(model.organization_id == source_id))
            == 0
        )

    target_billing = (
        await db.execute(select(BillingAccount).where(BillingAccount.organization_id == target_id))
    ).scalar_one()
    assert target_billing.stripe_customer_id == "cus_target"
    assert (
        await db.scalar(
            select(func.count(BillingAccount.id)).where(BillingAccount.organization_id == source_id)
        )
        == 0
    )

    limits = (
        await db.execute(
            select(MemberCreditLimit.user_id, MemberCreditLimit.monthly_limit)
            .where(MemberCreditLimit.organization_id == target_id)
            .order_by(MemberCreditLimit.monthly_limit)
        )
    ).all()
    assert set(limits) == {(admin_id, 10), (member_id, 12)}

    audit = (
        await db.execute(select(AdminAuditEntry).where(AdminAuditEntry.action == "org.merge"))
    ).scalar_one()
    assert audit.actor_user_id == admin_id
    assert audit.target_id == target_id
    assert audit.meta == {"source_id": str(source_id), "members_moved": 2}


async def test_merge_organizations_rejects_target_in_source_list(client, db):
    _, headers = await _superuser(client, db, email="admin@invalid-merge.com")
    target = await create_org(client, headers, name="Target Co")

    res = await client.post(
        "/api/admin/organizations/merge",
        json={"target_id": target["id"], "source_ids": [target["id"]]},
        headers=headers,
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "ERR_ADM_008"


# ── Deactivate / reactivate ───────────────────────────────────────────


async def test_deactivate_then_reactivate_user(client, db):
    _, headers = await _superuser(client, db)
    target, target_headers = await register_and_login(client, "member@example.com")
    target_id = uuid.UUID(target["id"])

    # Deactivate.
    res = await client.post(f"/api/admin/users/{target['id']}/deactivate", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False
    db.expire_all()
    user = await db.get(User, target_id)
    assert user.is_active is False

    # Deactivation is enforced in auth: login is rejected while inactive.
    login_res = await client.post(
        "/api/auth/login", json={"email": "member@example.com", "password": "correct-horse9"}
    )
    assert login_res.status_code == 401, login_res.text
    assert login_res.json()["code"] == "ERR_AUTH_001"
    # The pre-deactivation token also stops working (per-request DB is_active check).
    me = await client.get("/api/auth/me", headers=target_headers)
    assert me.status_code == 401

    # Reactivate.
    res = await client.post(f"/api/admin/users/{target['id']}/reactivate", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is True
    db.expire_all()
    user = await db.get(User, target_id)
    assert user.is_active is True

    # Login works again.
    login_res = await client.post(
        "/api/auth/login", json={"email": "member@example.com", "password": "correct-horse9"}
    )
    assert login_res.status_code == 200, login_res.text


async def test_deactivate_unknown_user_404(client, db):
    _, headers = await _superuser(client, db)
    res = await client.post(f"/api/admin/users/{uuid.uuid4()}/deactivate", headers=headers)
    assert res.status_code == 404, res.text
    assert res.json()["code"] == "ERR_ADM_001"


async def test_cannot_deactivate_self(client, db):
    admin, headers = await _superuser(client, db)
    res = await client.post(f"/api/admin/users/{admin['id']}/deactivate", headers=headers)
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "ERR_ADM_003"


# ── Error record lookup ───────────────────────────────────────────────


async def test_error_lookup_unknown_id_404(client, db):
    _, headers = await _superuser(client, db)
    # Reads Redis; a random ref has no stored context -> admin error-record code.
    res = await client.get(f"/api/admin/errors/{uuid.uuid4()}", headers=headers)
    assert res.status_code == 404, res.text
    assert res.json()["code"] == "ERR_ADM_004"
