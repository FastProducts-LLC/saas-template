"""Per-member credit limit endpoints + enforcement through a metered route.

Memberships for non-owner users are inserted directly through the db fixture
(the invitation flow is exercised in test_organizations.py; here it's just
setup noise).
"""

import uuid

import pytest

from app.core.config import settings
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.organizations.domain import Membership, Role
from tests.helpers import create_org, register_and_login


async def _org_with_member(client, db, owner_email: str, member_email: str):
    """Owner + org + a plain MEMBER. Returns (owner_headers, member_headers,
    org_id, member_user_id)."""
    _, owner_headers = await register_and_login(client, owner_email)
    org = await create_org(client, owner_headers)
    member_user, member_headers = await register_and_login(client, member_email)

    db.add(
        Membership(
            organization_id=uuid.UUID(org["id"]),
            user_id=uuid.UUID(member_user["id"]),
            role=Role.MEMBER,
        )
    )
    await db.commit()
    return owner_headers, member_headers, org["id"], member_user["id"]


async def test_member_limit_crud_roundtrip(client, db):
    owner, _, org_id, member_id = await _org_with_member(
        client, db, "limit-owner@example.com", "limit-member@example.com"
    )

    res = await client.put(
        f"/api/orgs/{org_id}/credits/member-limits/{member_id}",
        json={"monthly_limit": 25},
        headers=owner,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["monthly_limit"] == 25
    assert body["email"] == "limit-member@example.com"
    assert body["used_this_period"] == 0

    # Upsert: PUT again with a new cap updates in place.
    res = await client.put(
        f"/api/orgs/{org_id}/credits/member-limits/{member_id}",
        json={"monthly_limit": 40},
        headers=owner,
    )
    assert res.status_code == 200
    assert res.json()["monthly_limit"] == 40

    res = await client.get(f"/api/orgs/{org_id}/credits/member-limits", headers=owner)
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["user_id"] == member_id

    res = await client.delete(
        f"/api/orgs/{org_id}/credits/member-limits/{member_id}", headers=owner
    )
    assert res.status_code == 204
    res = await client.get(f"/api/orgs/{org_id}/credits/member-limits", headers=owner)
    assert res.json() == []

    # Idempotent delete.
    res = await client.delete(
        f"/api/orgs/{org_id}/credits/member-limits/{member_id}", headers=owner
    )
    assert res.status_code == 204


async def test_member_limits_require_admin(client, db):
    _, member, org_id, member_id = await _org_with_member(
        client, db, "gate-owner@example.com", "gate-member@example.com"
    )

    res = await client.get(f"/api/orgs/{org_id}/credits/member-limits", headers=member)
    assert res.status_code == 403
    res = await client.put(
        f"/api/orgs/{org_id}/credits/member-limits/{member_id}",
        json={"monthly_limit": 10},
        headers=member,
    )
    assert res.status_code == 403


async def test_set_limit_on_non_member_is_404(client, db):
    _, owner_headers = await register_and_login(client, "solo-owner@example.com")
    org = await create_org(client, owner_headers)
    stranger, _ = await register_and_login(client, "stranger@example.com")

    res = await client.put(
        f"/api/orgs/{org['id']}/credits/member-limits/{stranger['id']}",
        json={"monthly_limit": 10},
        headers=owner_headers,
    )
    assert res.status_code == 404, res.text
    assert res.json()["code"] == "ERR_CRD_007"


@pytest.fixture(autouse=True)
def _llm_route_stubs(monkeypatch):
    """Make the LLM complete route usable as the metered vehicle: a fake
    provider key passes the fail-fast config check, and enqueue is a no-op so
    no worker (with its own dev-DB session) ever runs."""
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)

    async def _noop(call_id):
        return None

    monkeypatch.setattr("app.domains.llm.interface.router.enqueue_llm_call", _noop)


def _complete_payload():
    return {"provider": "gemini", "prompt": "hello"}


async def test_member_at_cap_gets_409_on_metered_route(client, db):
    owner, member, org_id, member_id = await _org_with_member(
        client, db, "cap-owner@example.com", "cap-member@example.com"
    )
    # Orgs start with zero credits (no free allowance) — seed the wallet so
    # the member cap, not the org balance, is what refuses the second call.
    await build_credit_engine(db).grant(uuid.UUID(org_id), 50, "Test seed")
    await db.commit()

    res = await client.put(
        f"/api/orgs/{org_id}/credits/member-limits/{member_id}",
        json={"monthly_limit": 1},
        headers=owner,
    )
    assert res.status_code == 200

    # LLM_CALL costs 1: the first call fits the cap exactly...
    res = await client.post(
        f"/api/orgs/{org_id}/llm/complete",
        json=_complete_payload(),
        headers=member,
    )
    assert res.status_code == 202, res.text

    # ...the second would cross it and is refused before any charge.
    res = await client.post(
        f"/api/orgs/{org_id}/llm/complete",
        json=_complete_payload(),
        headers=member,
    )
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "ERR_CRD_006"

    # The owner (no limit row) is unaffected.
    res = await client.post(
        f"/api/orgs/{org_id}/llm/complete",
        json=_complete_payload(),
        headers=owner,
    )
    assert res.status_code == 202, res.text
