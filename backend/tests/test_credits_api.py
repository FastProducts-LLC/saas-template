"""Credit engine HTTP surface: action catalog, wallet summary, history,
credit packs, pack checkout (Stripe unconfigured in tests), and tenancy."""

from datetime import UTC, datetime

from app.domains.credits.domain import CREDIT_PACKS
from tests.helpers import create_org, register_and_login


async def _auth_org(client, email: str) -> tuple[dict, str]:
    """Register + login a user and create an org. Returns (headers, org_id)."""
    _, headers = await register_and_login(client, email)
    org = await create_org(client, headers)
    return headers, org["id"]


async def test_list_action_costs(client):
    res = await client.get("/api/credits/actions")
    assert res.status_code == 200, res.text
    actions = {a["action"]: a for a in res.json()}
    # llm_call / image / video actions are present, each with an integer cost.
    assert "llm_call" in actions
    assert any(a.startswith("image_") for a in actions)
    assert any(a.startswith("video_") for a in actions)
    for spec in actions.values():
        assert isinstance(spec["cost"], int)


async def test_wallet_summary_free_org_gets_no_credits(client):
    # No monthly allowance: a fresh org's first wallet touch yields a zero
    # balance — free orgs validate via identity checks, they don't browse.
    headers, org = await _auth_org(client, "owner@example.com")
    res = await client.get(f"/api/orgs/{org}/credits", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["balance"] == 0
    assert body["monthly_allowance"] == 0
    assert body["reserved"] == 0
    assert body["allowance_period"] == datetime.now(UTC).strftime("%Y-%m")


async def test_wallet_history_has_no_free_grant(client):
    headers, org = await _auth_org(client, "owner@example.com")
    res = await client.get(f"/api/orgs/{org}/credits/history", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_list_credit_packs_not_purchasable_without_stripe(client):
    # No Stripe config in tests, so every pack reports purchasable=False.
    res = await client.get("/api/billing/credits/packs")
    assert res.status_code == 200, res.text
    packs = res.json()
    assert len(packs) == len(CREDIT_PACKS)
    assert all(p["purchasable"] is False for p in packs)


async def test_pack_checkout_conflicts_when_stripe_unconfigured(client):
    headers, org = await _auth_org(client, "owner@example.com")
    # The org creator is OWNER, so the role check passes; the use case then
    # rejects because Stripe is not configured (ERR_BILL_001).
    res = await client.post(
        f"/api/orgs/{org}/billing/credits/checkout",
        json={"pack": "starter"},
        headers=headers,
    )
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "ERR_BILL_001"


async def test_tenancy_other_orgs_credits_404(client):
    _, org_a = await _auth_org(client, "alice@alice-credits.com")
    headers_b, _ = await _auth_org(client, "bob@bob-credits.com")
    # Bob is not a member of Alice's org — fetching its credits 404s.
    res = await client.get(f"/api/orgs/{org_a}/credits", headers=headers_b)
    assert res.status_code == 404, res.text
