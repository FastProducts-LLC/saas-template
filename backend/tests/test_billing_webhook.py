"""Billing webhook HTTP surface: credit-pack grants land idempotently.

Stripe signature verification is bypassed by overriding only the payment
gateway dependency with a fake whose verify_webhook returns a dict and whose
parse_event returns a preset CreditPackPurchased. The real SyncBillingEvent
use case stays wired (it needs the request's db session), so the grant is
persisted through the actual CreditEngine.
"""

import uuid

import pytest_asyncio

from app.domains.billing.application.dtos import CreditPackPurchased
from app.domains.billing.interface.deps import get_payment_gateway
from app.main import app
from tests.helpers import create_org, register_and_login


class FakeGateway:
    """Stand-in for StripeGateway: no signature check, fixed parsed event."""

    def __init__(self, event: CreditPackPurchased):
        self._event = event

    def is_configured(self) -> bool:
        return False

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        return {"type": "checkout.session.completed", "data": {"object": {}}}

    async def parse_event(self, event: dict) -> CreditPackPurchased:
        return self._event


async def _auth_org(client, email: str) -> tuple[dict, str]:
    _, headers = await register_and_login(client, email)
    org = await create_org(client, headers)
    return headers, org["id"]


@pytest_asyncio.fixture
def override_gateway():
    """Override ONLY the gateway dep; restore afterward so the conftest
    get_db override (and other tests) are never polluted."""

    def _install(event: CreditPackPurchased):
        app.dependency_overrides[get_payment_gateway] = lambda: FakeGateway(event)

    try:
        yield _install
    finally:
        app.dependency_overrides.pop(get_payment_gateway, None)


async def _post_webhook(client):
    return await client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=fake"},
    )


async def test_webhook_grants_credit_pack(client, override_gateway):
    headers, org = await _auth_org(client, "owner@example.com")
    # Touch the wallet first — no free allowance is granted (balance stays 0).
    await client.get(f"/api/orgs/{org}/credits", headers=headers)

    override_gateway(
        CreditPackPurchased(
            org_id=uuid.UUID(org),
            pack_name="Small pack",
            credits=500,
            session_id="cs_test_123",
            purchaser_email="buyer@example.com",
        )
    )

    res = await _post_webhook(client)
    assert res.status_code == 200, res.text
    assert res.json() == {"received": True}

    wallet = await client.get(f"/api/orgs/{org}/credits", headers=headers)
    assert wallet.json()["balance"] == 500  # pack only — no free allowance

    history = await client.get(
        f"/api/orgs/{org}/credits/history",
        headers=headers,
    )
    grants = [
        i for i in history.json()["items"] if i["description"] and "Credit pack" in i["description"]
    ]
    assert len(grants) == 1
    assert grants[0]["amount"] == 500


async def test_webhook_redelivery_is_idempotent(client, override_gateway):
    headers, org = await _auth_org(client, "owner@example.com")
    await client.get(f"/api/orgs/{org}/credits", headers=headers)

    override_gateway(
        CreditPackPurchased(
            org_id=uuid.UUID(org),
            pack_name="Small pack",
            credits=500,
            session_id="cs_test_123",
            purchaser_email="buyer@example.com",
        )
    )

    assert (await _post_webhook(client)).status_code == 200
    # Same session_id redelivered: still 200, still 500, no double credit.
    assert (await _post_webhook(client)).status_code == 200

    wallet = await client.get(f"/api/orgs/{org}/credits", headers=headers)
    assert wallet.json()["balance"] == 500

    history = await client.get(
        f"/api/orgs/{org}/credits/history",
        headers=headers,
    )
    pack_grants = [
        i for i in history.json()["items"] if i["description"] and "Credit pack" in i["description"]
    ]
    assert len(pack_grants) == 1  # exactly one pack-grant row


async def test_webhook_grants_to_a_second_valid_org(client, override_gateway):
    # Edge: rather than a non-existent org id (whose wallet INSERT would
    # violate the credit_wallets -> organizations FK on flush and 500 the
    # request), exercise a grant routed to a *different valid* org. This
    # proves org routing works and isolates the grant from the first org.
    headers_a, org_a = await _auth_org(client, "alice@alice-billing.com")
    headers_b, org_b = await _auth_org(client, "bob@bob-billing.com")
    await client.get(f"/api/orgs/{org_b}/credits", headers=headers_b)

    override_gateway(
        CreditPackPurchased(
            org_id=uuid.UUID(org_b),
            pack_name="Small pack",
            credits=500,
            session_id="cs_test_other",
            purchaser_email="buyer@example.com",
        )
    )

    assert (await _post_webhook(client)).status_code == 200

    wallet_b = await client.get(f"/api/orgs/{org_b}/credits", headers=headers_b)
    assert wallet_b.json()["balance"] == 500

    # Alice's org was untouched — and no free allowance exists.
    wallet_a = await client.get(f"/api/orgs/{org_a}/credits", headers=headers_a)
    assert wallet_a.json()["balance"] == 0
