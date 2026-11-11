"""Community subscription webhook plumbing: gateway event translation and
end-to-end membership updates through the real SyncBillingEvent dispatch."""

import uuid
from datetime import UTC, datetime

import pytest_asyncio

from app.domains.billing.application.dtos import (
    CommunitySubscriptionActivated,
    CommunitySubscriptionEnded,
    CommunitySubscriptionSynced,
    CreditPackPurchased,
)
from app.domains.billing.infrastructure.stripe_gateway import StripeGateway
from app.domains.billing.interface.deps import get_payment_gateway
from app.domains.community.domain import SubscriptionStatus
from app.main import app
from tests.helpers import make_superuser, register_and_login

# ---------------------------------------------------------------- parse_event

USER_ID = uuid.uuid4()


def _event(etype: str, obj: dict) -> dict:
    return {"type": etype, "data": {"object": obj}}


def _community_sub(**overrides) -> dict:
    sub = {
        "id": "sub_123",
        "status": "active",
        "cancel_at_period_end": False,
        "metadata": {"community_membership": "1", "user_id": str(USER_ID)},
        "items": {"data": [{"current_period_end": 1893456000}]},  # 2030-01-01
    }
    sub.update(overrides)
    return sub


async def test_parse_community_checkout_completed():
    event = _event(
        "checkout.session.completed",
        {
            "id": "cs_1",
            "mode": "subscription",
            "customer": "cus_1",
            "subscription": "sub_123",
            "metadata": {"community_membership": "1", "user_id": str(USER_ID)},
            "customer_details": {"email": "member@example.com"},
        },
    )
    parsed = await StripeGateway().parse_event(event)
    assert parsed == CommunitySubscriptionActivated(
        user_id=USER_ID,
        stripe_customer_id="cus_1",
        subscription_id="sub_123",
        purchaser_email="member@example.com",
    )


async def test_parse_untagged_subscription_checkout_ignored():
    event = _event(
        "checkout.session.completed",
        {
            "id": "cs_1",
            "mode": "subscription",
            "customer": "cus_1",
            "subscription": "sub_9",
            "metadata": {},
        },
    )
    assert await StripeGateway().parse_event(event) is None


async def test_parse_subscription_updated_reads_item_level_period_end():
    parsed = await StripeGateway().parse_event(
        _event("customer.subscription.updated", _community_sub(status="past_due"))
    )
    assert isinstance(parsed, CommunitySubscriptionSynced)
    assert parsed.status is SubscriptionStatus.PAST_DUE
    assert parsed.current_period_end == datetime.fromtimestamp(1893456000, tz=UTC)
    assert parsed.user_id == USER_ID


async def test_parse_subscription_top_level_period_end_fallback():
    sub = _community_sub()
    del sub["items"]
    sub["current_period_end"] = 1893456000
    parsed = await StripeGateway().parse_event(_event("customer.subscription.updated", sub))
    assert parsed.current_period_end == datetime.fromtimestamp(1893456000, tz=UTC)


async def test_parse_subscription_deleted():
    parsed = await StripeGateway().parse_event(
        _event("customer.subscription.deleted", _community_sub())
    )
    assert parsed == CommunitySubscriptionEnded(subscription_id="sub_123")


async def test_parse_untagged_subscription_events_ignored():
    sub = _community_sub(metadata={})
    for etype in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        assert await StripeGateway().parse_event(_event(etype, sub)) is None


async def test_parse_credit_pack_still_works():
    org_id = uuid.uuid4()
    event = _event(
        "checkout.session.completed",
        {
            "id": "cs_2",
            "mode": "payment",
            "client_reference_id": str(org_id),
            "metadata": {"credit_pack": "starter"},
            "customer_details": {"email": "buyer@example.com"},
        },
    )
    parsed = await StripeGateway().parse_event(event)
    assert isinstance(parsed, CreditPackPurchased)
    assert parsed.org_id == org_id


# ---------------------------------------------------------------- end to end


class FakeGateway:
    """No signature check; parse_event returns a queue of preset events."""

    def __init__(self, events):
        self._events = list(events)

    def is_configured(self) -> bool:
        return False

    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        return {"type": "noop", "data": {"object": {}}}

    async def parse_event(self, event: dict):
        return self._events.pop(0) if self._events else None


@pytest_asyncio.fixture
def override_gateway():
    def _install(*events):
        # One shared instance — each webhook POST consumes the next event.
        fake = FakeGateway(events)
        app.dependency_overrides[get_payment_gateway] = lambda: fake

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


async def _join_community(client, db, email: str) -> tuple[dict, uuid.UUID]:
    admin, admin_headers = await register_and_login(client, "sub-admin@example.com")
    await make_superuser(db, admin["id"])
    await client.put("/api/admin/flags/community", json={"enabled": True}, headers=admin_headers)
    user, headers = await register_and_login(client, email)
    res = await client.post(
        "/api/community/profile",
        json={"handle": "subscriber", "display_name": "Sub"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return headers, uuid.UUID(user["id"])


async def test_webhook_activates_then_syncs_then_ends(client, db, override_gateway):
    headers, user_id = await _join_community(client, db, "premium@example.com")
    period_end = datetime(2030, 1, 1, tzinfo=UTC)

    override_gateway(
        CommunitySubscriptionActivated(
            user_id=user_id, stripe_customer_id="cus_9", subscription_id="sub_9"
        ),
        CommunitySubscriptionSynced(
            subscription_id="sub_9",
            status=SubscriptionStatus.ACTIVE,
            current_period_end=period_end,
            cancel_at_period_end=False,
            user_id=user_id,
        ),
        CommunitySubscriptionEnded(subscription_id="sub_9"),
    )

    assert (await _post_webhook(client)).status_code == 200
    me = (await client.get("/api/community/me", headers=headers)).json()
    assert me["membership"]["tier"] == "premium"
    assert me["membership"]["is_premium"] is True

    assert (await _post_webhook(client)).status_code == 200
    me = (await client.get("/api/community/me", headers=headers)).json()
    assert me["membership"]["current_period_end"] is not None

    assert (await _post_webhook(client)).status_code == 200
    me = (await client.get("/api/community/me", headers=headers)).json()
    assert me["membership"]["tier"] == "free"
    assert me["membership"]["subscription_status"] == "canceled"
    assert me["membership"]["is_premium"] is False


async def test_sync_lands_by_user_id_when_it_outraces_activation(client, db, override_gateway):
    headers, user_id = await _join_community(client, db, "racer@example.com")

    override_gateway(
        CommunitySubscriptionSynced(
            subscription_id="sub_race",
            status=SubscriptionStatus.ACTIVE,
            current_period_end=datetime(2030, 1, 1, tzinfo=UTC),
            cancel_at_period_end=False,
            user_id=user_id,
        ),
    )
    assert (await _post_webhook(client)).status_code == 200
    me = (await client.get("/api/community/me", headers=headers)).json()
    assert me["membership"]["tier"] == "premium"


async def test_unknown_subscription_events_are_noops(client, db, override_gateway):
    headers, _ = await _join_community(client, db, "bystander@example.com")

    override_gateway(
        CommunitySubscriptionSynced(
            subscription_id="sub_unknown",
            status=SubscriptionStatus.ACTIVE,
            current_period_end=None,
            cancel_at_period_end=False,
            user_id=None,
        ),
        CommunitySubscriptionEnded(subscription_id="sub_unknown"),
    )
    assert (await _post_webhook(client)).status_code == 200
    assert (await _post_webhook(client)).status_code == 200

    me = (await client.get("/api/community/me", headers=headers)).json()
    assert me["membership"]["tier"] == "free"
    assert me["membership"]["subscription_status"] == "none"
