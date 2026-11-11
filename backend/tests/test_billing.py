"""Billing API tests: billing account, portal, invoices, webhook plumbing.

Two flavours:

  * Endpoint flows fake the payment gateway by monkeypatching the module-level
    `app.domains.billing.interface.deps._gateway` singleton with a
    `FakePaymentGateway` that satisfies the `PaymentGateway` protocol.
  * Webhook flows use the REAL `StripeGateway` so the actual HMAC verification
    and event-parsing paths run; only `settings` and the Stripe SDK functions
    the gateway calls are monkeypatched.

Credit-pack checkout + grant flows live in `test_billing_credit_pack.py`.
"""

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

import app.domains.billing.interface.deps as billing_deps
from app.core.config import settings
from app.domains.billing.domain import BillingAccount, InvoiceSummary
from tests.helpers import (
    create_org,
    register_and_login,
    stripe_signature,
)

# ── Fakes ────────────────────────────────────────────────────────────


class FakePaymentGateway:
    """In-memory PaymentGateway. Configured/purchasable by default; flip the
    flags per test. Records the customer/checkout/portal calls it receives so
    tests can assert on side effects."""

    def __init__(self, configured: bool = True, invoices: list[InvoiceSummary] | None = None):
        self.configured = configured
        self.invoices = invoices or []
        self.created_customers: list[dict] = []
        self.pack_checkout_calls: list[dict] = []
        self.portal_calls: list[dict] = []
        self.list_invoices_calls: list[str] = []

    def is_configured(self) -> bool:
        return self.configured

    def is_pack_purchasable(self, pack) -> bool:
        return self.configured

    async def create_customer(self, *, email: str, name: str, org_id: str) -> str:
        self.created_customers.append({"email": email, "name": name, "org_id": org_id})
        return f"cus_fake_{len(self.created_customers)}"

    async def create_credit_pack_checkout_url(
        self, *, customer_id: str, pack, org_id: str, user_id: str | None = None
    ) -> str:
        self.pack_checkout_calls.append(
            {"customer_id": customer_id, "pack": pack, "org_id": org_id, "user_id": user_id}
        )
        return "https://checkout.stripe.test/pack"

    async def create_portal_url(self, *, customer_id: str) -> str:
        self.portal_calls.append(customer_id)
        return "https://portal.stripe.test/session"

    async def list_invoices(self, *, customer_id: str, limit: int = 12) -> list[InvoiceSummary]:
        self.list_invoices_calls.append(customer_id)
        return self.invoices

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        raise NotImplementedError

    async def parse_event(self, event: dict):
        raise NotImplementedError


def _fake_invoice(suffix: str = "1") -> InvoiceSummary:
    return InvoiceSummary(
        id=f"in_{suffix}",
        number=f"INV-{suffix}",
        status="paid",
        amount_due=2900,
        currency="usd",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        hosted_invoice_url=f"https://invoice.stripe.test/{suffix}",
        invoice_pdf=f"https://invoice.stripe.test/{suffix}.pdf",
    )


def use_fake_gateway(monkeypatch, gateway: FakePaymentGateway) -> FakePaymentGateway:
    """Swap the billing composition-root singleton; auto-restored by monkeypatch.

    The deps build use cases by closing over the module-level `_gateway`, so
    patching the attribute is enough for every endpoint that consumes it."""
    monkeypatch.setattr(billing_deps, "_gateway", gateway)
    return gateway


async def add_member(db, org_id: str, user_id: str) -> None:
    """Seed a plain (non-admin) membership directly — the invite token is never
    returned over the API, so we bypass the invite flow for role tests."""
    from app.domains.organizations.domain import Membership, Role

    db.add(
        Membership(
            organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            role=Role.MEMBER,
        )
    )
    await db.commit()


async def buy_pack_to_attach_customer(client, headers, org_id: str) -> None:
    """Run a pack checkout so the org gets a Stripe customer attached."""
    res = await client.post(
        f"/api/orgs/{org_id}/billing/credits/checkout",
        json={"pack": "starter"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


# ── Billing account ──────────────────────────────────────────────────


async def test_get_billing_creates_account_row_for_member(client, db, monkeypatch):
    use_fake_gateway(monkeypatch, FakePaymentGateway())
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    res = await client.get(f"/api/orgs/{org['id']}/billing", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"has_billing_account": False}

    row = (
        await db.execute(
            select(BillingAccount).where(BillingAccount.organization_id == uuid.UUID(org["id"]))
        )
    ).scalar_one()
    assert row.stripe_customer_id is None


async def test_get_billing_rejects_non_member(client, monkeypatch):
    use_fake_gateway(monkeypatch, FakePaymentGateway())
    _, owner_headers = await register_and_login(client, email="owner@example.com")
    org = await create_org(client, owner_headers)
    _, outsider_headers = await register_and_login(client, email="outsider@example.com")

    res = await client.get(f"/api/orgs/{org['id']}/billing", headers=outsider_headers)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_PERM_002"


async def test_pack_checkout_attaches_customer_to_billing_account(client, db, monkeypatch):
    gateway = use_fake_gateway(monkeypatch, FakePaymentGateway())
    user, headers = await register_and_login(client)
    org = await create_org(client, headers)

    await buy_pack_to_attach_customer(client, headers, org["id"])

    assert len(gateway.created_customers) == 1
    row = (
        await db.execute(
            select(BillingAccount).where(BillingAccount.organization_id == uuid.UUID(org["id"]))
        )
    ).scalar_one()
    assert row.stripe_customer_id is not None
    assert gateway.pack_checkout_calls[0]["customer_id"] == row.stripe_customer_id
    # The buyer's id rides along so the purchase can be attributed in analytics.
    assert gateway.pack_checkout_calls[0]["user_id"] == user["id"]

    res = await client.get(f"/api/orgs/{org['id']}/billing", headers=headers)
    assert res.json() == {"has_billing_account": True}


# ── Portal ───────────────────────────────────────────────────────────


async def test_portal_returns_url_once_billing_account_exists(client, monkeypatch):
    gateway = use_fake_gateway(monkeypatch, FakePaymentGateway())
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    # A pack checkout first attaches a customer (a billing account).
    await buy_pack_to_attach_customer(client, headers, org["id"])

    res = await client.post(f"/api/orgs/{org['id']}/billing/portal", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["url"] == "https://portal.stripe.test/session"
    assert gateway.portal_calls  # the customer id was forwarded


async def test_portal_without_billing_account(client, monkeypatch):
    use_fake_gateway(monkeypatch, FakePaymentGateway())
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    res = await client.post(f"/api/orgs/{org['id']}/billing/portal", headers=headers)
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_BILL_004"


# ── Invoices ─────────────────────────────────────────────────────────


async def test_invoices_empty_when_no_billing_account(client, monkeypatch):
    use_fake_gateway(monkeypatch, FakePaymentGateway(invoices=[_fake_invoice()]))
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    res = await client.get(f"/api/orgs/{org['id']}/billing/invoices", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_invoices_mapped_when_billing_account_exists(client, monkeypatch):
    gateway = use_fake_gateway(monkeypatch, FakePaymentGateway(invoices=[_fake_invoice("7")]))
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    await buy_pack_to_attach_customer(client, headers, org["id"])

    res = await client.get(f"/api/orgs/{org['id']}/billing/invoices", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    inv = body[0]
    assert inv["id"] == "in_7"
    assert inv["number"] == "INV-7"
    assert inv["status"] == "paid"
    assert inv["amount_due"] == 2900
    assert inv["currency"] == "usd"
    assert inv["hosted_invoice_url"] == "https://invoice.stripe.test/7"
    assert inv["invoice_pdf"] == "https://invoice.stripe.test/7.pdf"
    assert gateway.list_invoices_calls  # read through to the provider


async def test_invoices_rejects_member_without_admin_role(client, db, monkeypatch):
    use_fake_gateway(monkeypatch, FakePaymentGateway())
    _, owner_headers = await register_and_login(client, email="owner@example.com")
    org = await create_org(client, owner_headers)

    member, member_headers = await register_and_login(client, email="member@example.com")
    await add_member(db, org["id"], member["id"])

    res = await client.get(f"/api/orgs/{org['id']}/billing/invoices", headers=member_headers)
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_PERM_001"


async def test_invoices_empty_when_gateway_unconfigured(client, monkeypatch):
    use_fake_gateway(monkeypatch, FakePaymentGateway(configured=False, invoices=[_fake_invoice()]))
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    res = await client.get(f"/api/orgs/{org['id']}/billing/invoices", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


# ── Webhook (real StripeGateway) ─────────────────────────────────────

WEBHOOK_SECRET = "whsec_test"


def _configure_stripe(monkeypatch) -> None:
    """Wire the real gateway's settings so HMAC verification resolves."""
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)


async def test_webhook_rejected_when_secret_unset(client, monkeypatch):
    """An empty STRIPE_WEBHOOK_SECRET must not verify: a signature computed
    with "" is one any attacker can produce (forged checkout.session.completed
    = free credits)."""
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    payload = _event("checkout.session.completed", {"mode": "payment"})
    res = await client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": stripe_signature(payload, "")},
    )
    assert res.status_code == 400, res.text


def _post_webhook(client, payload: bytes):
    return client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": stripe_signature(payload, WEBHOOK_SECRET)},
    )


def _event(event_type: str, obj: dict) -> bytes:
    """Full event envelope — construct_event needs id/object/api_version,
    not just type/data."""
    return json.dumps(
        {
            "id": "evt_test_1",
            "object": "event",
            "api_version": "2024-06-20",
            "type": event_type,
            "data": {"object": obj},
        }
    ).encode()


async def test_webhook_rejects_bad_signature(client, monkeypatch):
    _configure_stripe(monkeypatch)
    payload = json.dumps({"type": "ping", "data": {"object": {}}}).encode()

    res = await client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert res.status_code == 400


async def test_webhook_subscription_events_are_ignored(client, monkeypatch):
    """Legacy subscription lifecycle events are no longer meaningful — the
    webhook acknowledges them without doing anything."""
    _configure_stripe(monkeypatch)

    payload = _event(
        "customer.subscription.updated",
        {"id": "sub_1", "customer": "cus_1", "status": "past_due"},
    )
    res = await _post_webhook(client, payload)
    assert res.status_code == 200, res.text


async def test_webhook_unknown_event_is_noop(client, db, monkeypatch):
    _configure_stripe(monkeypatch)

    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    payload = _event("invoice.payment_failed", {"id": "in_1"})

    res = await _post_webhook(client, payload)
    assert res.status_code == 200, res.text

    # No billing account row was created/changed by an ignored event type.
    rows = (
        (
            await db.execute(
                select(BillingAccount).where(BillingAccount.organization_id == uuid.UUID(org["id"]))
            )
        )
        .scalars()
        .all()
    )
    assert rows == []
