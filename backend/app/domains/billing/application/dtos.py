"""Billing application DTOs: neutral webhook-event commands."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domains.billing.domain.entities import Subscription
from app.domains.billing.domain.value_objects import BillingInterval, Plan, PlanSubscriptionStatus
from app.domains.community.domain import SubscriptionStatus


@dataclass(frozen=True)
class CreditPackPurchased:
    """A one-time credit-pack checkout completed (mode=payment)."""

    org_id: uuid.UUID
    pack_name: str
    credits: int
    # Stripe checkout session id — the grant's idempotency key, so webhook
    # redelivery can never double-credit.
    session_id: str
    purchaser_email: str | None = None
    # Product-analytics attribution (`credit_pack_purchased`). `user_id` is
    # the member who started the checkout, stamped into the session metadata;
    # None for sessions created before that stamp existed.
    user_id: uuid.UUID | None = None
    pack: str | None = None  # catalog key, e.g. "growth"
    amount_cents: int | None = None  # catalog price, not Stripe's settled amount


@dataclass(frozen=True)
class CommunitySubscriptionActivated:
    """A community membership checkout completed (mode=subscription,
    metadata.community_membership=1). Period end arrives on the follow-up
    customer.subscription.* event."""

    user_id: uuid.UUID
    stripe_customer_id: str
    subscription_id: str
    purchaser_email: str | None = None


@dataclass(frozen=True)
class CommunitySubscriptionSynced:
    """customer.subscription.created/updated for a community-tagged
    subscription. `user_id` (from subscription metadata) lets the sync land
    even when this event outraces checkout.session.completed."""

    subscription_id: str
    status: SubscriptionStatus
    current_period_end: datetime | None
    cancel_at_period_end: bool
    user_id: uuid.UUID | None = None


@dataclass(frozen=True)
class CommunitySubscriptionEnded:
    """customer.subscription.deleted — the membership downgrades to free."""

    subscription_id: str


@dataclass(frozen=True)
class OrgSubscriptionChanged:
    subscription_id: str
    org_id: uuid.UUID | None = None


@dataclass(frozen=True)
class SubscriptionSnapshot:
    subscription_id: str
    org_id: uuid.UUID | None
    user_id: uuid.UUID | None
    plan: Plan | None
    interval: BillingInterval | None
    status: PlanSubscriptionStatus
    current_period_end: datetime | None
    cancel_at_period_end: bool
    is_org_plan: bool


BillingEvent = (
    OrgSubscriptionChanged
    | CreditPackPurchased
    | CommunitySubscriptionActivated
    | CommunitySubscriptionSynced
    | CommunitySubscriptionEnded
)


@dataclass(frozen=True)
class PlanOverview:
    plan: Plan
    subscription: Subscription | None


@dataclass(frozen=True)
class PlanCatalogRow:
    plan: Plan
    name: str
    monthly_price_cents: int
    annual_price_cents: int
    monthly_credits: int
    purchasable: dict[str, bool]
