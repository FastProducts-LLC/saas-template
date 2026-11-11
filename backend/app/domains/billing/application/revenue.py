"""Read-only revenue queries and provider reconciliation.

Live means active, trialing, or past due. Display groups round independently,
so their MRR sum can differ from the exact-total rounded MRR by a cent.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from typing import TYPE_CHECKING

from app.domains.billing.domain.value_objects import (
    PLANS,
    BillingInterval,
    Plan,
)
from app.domains.billing.domain.value_objects import (
    PlanSubscriptionStatus as Status,
)

if TYPE_CHECKING:
    from app.domains.billing.application.ports import RevenueGateway, RevenueReader

# Matches the currency used to provision catalog prices in scripts/stripe_sync.py.
CURRENCY = "usd"
LIVE_STATUSES = (Status.ACTIVE, Status.TRIALING, Status.PAST_DUE)
MRR_STATUSES = (Status.ACTIVE, Status.PAST_DUE)


@dataclass(frozen=True)
class RevenueGroup:
    plan: Plan
    interval: BillingInterval
    status: Status
    count: int
    canceling: int
    new_last_30d: int
    canceled_last_30d: int


@dataclass(frozen=True)
class RevenueSubscription:
    subscription_id: str
    org_id: uuid.UUID | None
    plan: Plan | None
    interval: BillingInterval | None
    status: Status


@dataclass(frozen=True)
class PlanRevenue:
    plan: Plan
    interval: BillingInterval
    count: int
    mrr_cents: int


@dataclass(frozen=True)
class RevenueReport:
    currency: str
    mrr_cents: int
    arr_cents: int
    active: int
    trialing: int
    past_due: int
    canceling: int
    by_plan: list[PlanRevenue]
    new_last_30d: int
    canceled_last_30d: int
    computed_at: datetime


def exact_mrr(plan: Plan | None, interval: BillingInterval | None, status: Status) -> Fraction:
    if status not in MRR_STATUSES or plan not in PLANS or interval is None:
        return Fraction(0)
    spec = PLANS[plan]
    if interval == BillingInterval.ANNUAL:
        return Fraction(spec.annual_price_cents, 12)
    return Fraction(spec.monthly_price_cents)


def round_cents(value: Fraction) -> int:
    """Round nonnegative catalog revenue to whole cents, with ties upward."""
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


class GetRevenue:
    def __init__(self, reader: "RevenueReader") -> None:
        self.reader = reader

    async def execute(self, *, now: datetime | None = None) -> RevenueReport:
        now = now or datetime.now(UTC)
        groups = await self.reader.grouped_revenue(now)
        total = sum((exact_mrr(g.plan, g.interval, g.status) * g.count for g in groups), Fraction())
        by_plan = []
        for plan in PLANS:
            if plan == Plan.FREE:
                continue
            for interval in BillingInterval:
                matching = [g for g in groups if g.plan == plan and g.interval == interval]
                by_plan.append(
                    PlanRevenue(
                        plan,
                        interval,
                        sum(g.count for g in matching if g.status in LIVE_STATUSES),
                        round_cents(
                            sum(
                                (
                                    exact_mrr(g.plan, g.interval, g.status) * g.count
                                    for g in matching
                                ),
                                Fraction(),
                            )
                        ),
                    )
                )
        mrr = round_cents(total)
        return RevenueReport(
            currency=CURRENCY,
            mrr_cents=mrr,
            arr_cents=mrr * 12,
            active=sum(g.count for g in groups if g.status == Status.ACTIVE),
            trialing=sum(g.count for g in groups if g.status == Status.TRIALING),
            past_due=sum(g.count for g in groups if g.status == Status.PAST_DUE),
            canceling=sum(g.canceling for g in groups),
            by_plan=by_plan,
            new_last_30d=sum(g.new_last_30d for g in groups),
            canceled_last_30d=sum(g.canceled_last_30d for g in groups),
            computed_at=now,
        )


@dataclass(frozen=True)
class RevenueDrift:
    kind: str
    subscription_id: str
    org_id: uuid.UUID | None
    local_value: str | None = None
    stripe_value: str | None = None


@dataclass(frozen=True)
class ReconcileReport:
    drift: list[RevenueDrift]
    local_mrr_cents: int
    stripe_mrr_cents: int
    in_sync: bool


class ReconcileRevenue:
    def __init__(self, reader: "RevenueReader", gateway: "RevenueGateway") -> None:
        self.reader = reader
        self.gateway = gateway

    async def execute(self) -> ReconcileReport:
        local = {s.subscription_id: s for s in await self.reader.list_subscriptions()}
        remote = {
            s.subscription_id: s
            for s in await self.gateway.list_org_plan_subscriptions()
            if s.is_org_plan
        }
        drift = []
        for subscription_id in sorted(local.keys() | remote.keys()):
            row, snapshot = local.get(subscription_id), remote.get(subscription_id)
            if row is None:
                if snapshot.status in LIVE_STATUSES:
                    drift.append(RevenueDrift("missing_locally", subscription_id, snapshot.org_id))
                continue
            if snapshot is None:
                if row.status in LIVE_STATUSES:
                    drift.append(RevenueDrift("missing_in_stripe", subscription_id, row.org_id))
                continue
            if row.status == snapshot.status == Status.CANCELED:
                continue
            for field in ("status", "plan", "interval"):
                left, right = getattr(row, field), getattr(snapshot, field)
                if left != right:
                    drift.append(
                        RevenueDrift(
                            f"{field}_mismatch",
                            subscription_id,
                            row.org_id,
                            left.value if left is not None else None,
                            right.value if right is not None else None,
                        )
                    )
        local_mrr = round_cents(
            sum((exact_mrr(s.plan, s.interval, s.status) for s in local.values()), Fraction())
        )
        stripe_mrr = round_cents(
            sum((exact_mrr(s.plan, s.interval, s.status) for s in remote.values()), Fraction())
        )
        return ReconcileReport(drift, local_mrr, stripe_mrr, not drift and local_mrr == stripe_mrr)
