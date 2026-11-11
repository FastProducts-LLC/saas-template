"""Billing webhook sync unit tests for credit-pack purchases.

SyncBillingEvent is constructed directly over a fake credit service and a
fake receipt mailer. No database, no HTTP client, no conftest fixtures used.
"""

import uuid

from app.domains.billing.application.dtos import CreditPackPurchased
from app.domains.billing.application.use_cases import SyncBillingEvent

# -- fakes --------------------------------------------------------------------


class FakeCreditService:
    def __init__(self, *, already: bool = False) -> None:
        self.already = already
        self.grants: list[dict] = []
        self.already_checks: list[str] = []

    async def already_granted(self, idempotency_key: str) -> bool:
        self.already_checks.append(idempotency_key)
        return self.already

    async def grant(self, org_id, amount, description, user_id=None, idempotency_key=None):
        self.grants.append(
            {
                "org_id": org_id,
                "amount": amount,
                "description": description,
                "idempotency_key": idempotency_key,
            }
        )
        return object()


class FakeReceiptMailer:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_credit_pack_receipt(self, email, pack_name, credits) -> None:
        self.sent.append({"email": email, "pack_name": pack_name, "credits": credits})

    async def get_by_provider_subscription_id(self, sub_id):
        raise AssertionError("subscription repo should not be touched")

    async def get_by_provider_customer_id(self, customer_id):
        raise AssertionError("subscription repo should not be touched")

    async def add(self, subscription):
        raise AssertionError("subscription repo should not be touched")


def make_event(
    *,
    org_id: uuid.UUID | None = None,
    purchaser_email: str | None = "buyer@example.com",
) -> CreditPackPurchased:
    return CreditPackPurchased(
        org_id=org_id or uuid.uuid4(),
        pack_name="Medium pack",
        credits=1_500,
        session_id="cs_test_123",
        purchaser_email=purchaser_email,
    )


# -- tests --------------------------------------------------------------------


async def test_credit_pack_grants_once_and_sends_receipt():
    credits = FakeCreditService(already=False)
    receipts = FakeReceiptMailer()
    sync = SyncBillingEvent(credits=credits, receipts=receipts)
    event = make_event()

    await sync.execute(event)

    assert credits.already_checks == ["cs_test_123"]
    assert len(credits.grants) == 1
    grant = credits.grants[0]
    assert grant["org_id"] == event.org_id
    assert grant["amount"] == 1_500
    assert grant["idempotency_key"] == "cs_test_123"
    assert "Medium pack" in grant["description"]
    assert "+1500" in grant["description"]

    assert receipts.sent == [
        {"email": "buyer@example.com", "pack_name": "Medium pack", "credits": 1_500}
    ]


async def test_credit_pack_already_granted_is_noop():
    credits = FakeCreditService(already=True)
    receipts = FakeReceiptMailer()
    sync = SyncBillingEvent(credits=credits, receipts=receipts)

    await sync.execute(make_event())

    assert credits.grants == []  # redelivery — no double grant
    assert receipts.sent == []  # and no receipt


async def test_credit_pack_no_email_grants_but_no_receipt():
    credits = FakeCreditService(already=False)
    receipts = FakeReceiptMailer()
    sync = SyncBillingEvent(credits=credits, receipts=receipts)

    await sync.execute(make_event(purchaser_email=None))

    assert len(credits.grants) == 1
    assert receipts.sent == []


async def test_credit_pack_no_credit_service_does_not_crash():
    receipts = FakeReceiptMailer()
    sync = SyncBillingEvent(credits=None, receipts=receipts)

    # Just a warning path — no crash, no receipt.
    await sync.execute(make_event())

    assert receipts.sent == []
