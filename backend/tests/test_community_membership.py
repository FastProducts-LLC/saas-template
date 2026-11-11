"""Unit tests for community membership checkout/portal gates and the
webhook-side subscription applier."""

import uuid
from datetime import UTC, datetime

import pytest

from app.domains.billing.domain import (
    BillingNotConfigured,
    CommunityPlanNotConfigured,
    NoBillingAccount,
)
from app.domains.community.application.use_cases import (
    ApplyCommunitySubscriptionEvent,
    CreateCommunityCheckout,
    CreateCommunityPortal,
)
from app.domains.community.domain import (
    AlreadyPremium,
    CommunityBanned,
    CommunityMembership,
    CommunityPlan,
    NotACommunityMember,
    SubscriptionStatus,
)


class FakeMembershipRepo:
    def __init__(self) -> None:
        self.items: list[CommunityMembership] = []

    async def add(self, membership):
        self.items.append(membership)

    async def get_by_user(self, user_id):
        return next((m for m in self.items if m.user_id == user_id), None)

    async def get_by_subscription_id(self, subscription_id):
        return next(
            (m for m in self.items if m.stripe_subscription_id == subscription_id),
            None,
        )


class FakeGateway:
    def __init__(self, *, configured=True, purchasable=True):
        self.configured = configured
        self.purchasable = purchasable
        self.created_customers: list[str] = []

    def is_configured(self):
        return self.configured

    def is_community_plan_purchasable(self, plan):
        return self.purchasable

    async def create_customer_for_user(self, *, email, name, user_id):
        self.created_customers.append(user_id)
        return f"cus_{len(self.created_customers)}"

    async def create_community_subscription_checkout_url(self, *, customer_id, plan, user_id):
        return f"https://checkout.example/{customer_id}/{plan.value}"

    async def create_portal_url(self, *, customer_id):
        return f"https://portal.example/{customer_id}"


class FakeUser:
    def __init__(self):
        self.id = uuid.uuid4()
        self.email = "member@example.com"
        self.first_name = "Mem"
        self.last_name = "Ber"


def _checkout(repo, gateway):
    return CreateCommunityCheckout(repo, gateway, grace_days=3)


async def test_checkout_requires_configured_stripe():
    with pytest.raises(BillingNotConfigured):
        await _checkout(FakeMembershipRepo(), FakeGateway(configured=False)).execute(
            FakeUser(), CommunityPlan.MONTHLY
        )


async def test_checkout_requires_purchasable_plan():
    with pytest.raises(CommunityPlanNotConfigured):
        await _checkout(FakeMembershipRepo(), FakeGateway(purchasable=False)).execute(
            FakeUser(), CommunityPlan.MONTHLY
        )


async def test_checkout_requires_membership():
    with pytest.raises(NotACommunityMember):
        await _checkout(FakeMembershipRepo(), FakeGateway()).execute(
            FakeUser(), CommunityPlan.MONTHLY
        )


async def test_checkout_rejects_banned_and_premium():
    repo, gateway, user = FakeMembershipRepo(), FakeGateway(), FakeUser()
    membership = CommunityMembership(user_id=user.id)
    membership.ban(by=uuid.uuid4())
    repo.items.append(membership)
    with pytest.raises(CommunityBanned):
        await _checkout(repo, gateway).execute(user, CommunityPlan.MONTHLY)

    membership.unban()
    membership.apply_subscription(
        subscription_id="sub_1",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=None,
        cancel_at_period_end=False,
    )
    with pytest.raises(AlreadyPremium):
        await _checkout(repo, gateway).execute(user, CommunityPlan.MONTHLY)


async def test_checkout_creates_customer_once_then_reuses():
    repo, gateway, user = FakeMembershipRepo(), FakeGateway(), FakeUser()
    membership = CommunityMembership(user_id=user.id)
    repo.items.append(membership)

    url = await _checkout(repo, gateway).execute(user, CommunityPlan.ANNUAL)
    assert url == "https://checkout.example/cus_1/annual"
    assert membership.stripe_customer_id == "cus_1"

    await _checkout(repo, gateway).execute(user, CommunityPlan.MONTHLY)
    assert gateway.created_customers == [str(user.id)]  # reused, not recreated


async def test_portal_requires_billing_history():
    repo, user = FakeMembershipRepo(), FakeUser()
    with pytest.raises(NotACommunityMember):
        await CreateCommunityPortal(repo, FakeGateway()).execute(user.id)

    membership = CommunityMembership(user_id=user.id)
    repo.items.append(membership)
    with pytest.raises(NoBillingAccount):
        await CreateCommunityPortal(repo, FakeGateway()).execute(user.id)

    membership.stripe_customer_id = "cus_7"
    url = await CreateCommunityPortal(repo, FakeGateway()).execute(user.id)
    assert url == "https://portal.example/cus_7"


# ---------------------------------------------------------------- webhook applier


async def test_activate_unknown_user_is_noop():
    repo = FakeMembershipRepo()
    await ApplyCommunitySubscriptionEvent(repo).activate(
        user_id=uuid.uuid4(), stripe_customer_id="cus_1", subscription_id="sub_1"
    )
    assert repo.items == []


async def test_activate_then_sync_then_end():
    repo = FakeMembershipRepo()
    user_id = uuid.uuid4()
    membership = CommunityMembership(user_id=user_id)
    repo.items.append(membership)
    applier = ApplyCommunitySubscriptionEvent(repo)

    await applier.activate(user_id=user_id, stripe_customer_id="cus_1", subscription_id="sub_1")
    assert membership.tier.value == "premium"
    assert membership.stripe_customer_id == "cus_1"

    period_end = datetime(2030, 1, 1, tzinfo=UTC)
    await applier.sync(
        subscription_id="sub_1",
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=period_end,
        cancel_at_period_end=True,
        user_id=None,
    )
    assert membership.subscription_status is SubscriptionStatus.PAST_DUE
    assert membership.current_period_end == period_end
    assert membership.cancel_at_period_end is True

    await applier.end(subscription_id="sub_1")
    assert membership.tier.value == "free"
    assert membership.stripe_subscription_id is None
    assert membership.stripe_customer_id == "cus_1"  # kept for resubscribe


async def test_sync_never_steals_another_subscription():
    repo = FakeMembershipRepo()
    user_id = uuid.uuid4()
    membership = CommunityMembership(user_id=user_id)
    membership.apply_subscription(
        subscription_id="sub_original",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=None,
        cancel_at_period_end=False,
    )
    repo.items.append(membership)

    await ApplyCommunitySubscriptionEvent(repo).sync(
        subscription_id="sub_other",
        status=SubscriptionStatus.CANCELED,
        current_period_end=None,
        cancel_at_period_end=False,
        user_id=user_id,
    )
    assert membership.stripe_subscription_id == "sub_original"
    assert membership.subscription_status is SubscriptionStatus.ACTIVE
