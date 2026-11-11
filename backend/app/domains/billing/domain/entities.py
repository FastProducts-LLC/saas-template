"""Organization billing accounts, subscription state, and provider-neutral invoices.

Credit packs and subscriptions share the organization billing account.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domains.billing.domain.value_objects import BillingInterval, Plan, PlanSubscriptionStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class InvoiceSummary:
    """Provider-neutral view of a past invoice. Invoices are never cached
    locally — they are read through from the provider on demand."""

    id: str
    number: str | None
    status: str  # draft, open, paid, void, uncollectible
    amount_due: int  # smallest currency unit (cents)
    currency: str
    created: datetime
    hosted_invoice_url: str | None
    invoice_pdf: str | None


@dataclass(eq=False)
class BillingAccount:
    organization_id: uuid.UUID
    stripe_customer_id: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def has_billing_account(self) -> bool:
        return self.stripe_customer_id is not None

    def attach_customer(self, customer_id: str) -> None:
        self.stripe_customer_id = customer_id


@dataclass(eq=False)
class Subscription:
    organization_id: uuid.UUID
    stripe_subscription_id: str
    plan: Plan
    interval: BillingInterval
    status: PlanSubscriptionStatus
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def effective_plan(self, *, grace_days: int, now: datetime | None = None) -> Plan:
        if self.status in (PlanSubscriptionStatus.ACTIVE, PlanSubscriptionStatus.TRIALING):
            return self.plan
        if self.status == PlanSubscriptionStatus.PAST_DUE and self.current_period_end is not None:
            if (now or _utcnow()) <= self.current_period_end + timedelta(days=grace_days):
                return self.plan
        return Plan.FREE

    def apply(
        self,
        *,
        stripe_subscription_id: str,
        plan: Plan,
        interval: BillingInterval,
        status: PlanSubscriptionStatus,
        current_period_end: datetime | None,
        cancel_at_period_end: bool,
    ) -> None:
        self.stripe_subscription_id = stripe_subscription_id
        self.plan = plan
        self.interval = interval
        self.status = status
        self.current_period_end = current_period_end
        self.cancel_at_period_end = cancel_at_period_end
        self.updated_at = _utcnow()
