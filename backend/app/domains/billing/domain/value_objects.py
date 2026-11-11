"""Organization plan catalog and subscription value objects."""

import enum
from dataclasses import dataclass


class Plan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class BillingInterval(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class PlanSubscriptionStatus(str, enum.Enum):
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


@dataclass(frozen=True)
class PlanSpec:
    plan: Plan
    name: str
    monthly_price_cents: int
    annual_price_cents: int
    monthly_credits: int | None

    def price_cents(self, interval: BillingInterval) -> int:
        if interval == BillingInterval.MONTHLY:
            return self.monthly_price_cents
        return self.annual_price_cents


PLANS: dict[Plan, PlanSpec] = {
    Plan.FREE: PlanSpec(Plan.FREE, "Free", 0, 0, None),
    Plan.PRO: PlanSpec(Plan.PRO, "Pro", 2900, 29000, 200),
    Plan.TEAM: PlanSpec(Plan.TEAM, "Team", 9900, 99000, 1000),
}
PAID_PLANS: tuple[Plan, ...] = (Plan.PRO, Plan.TEAM)
