"""Community membership plan catalog — the single source of truth for
displayed prices. The *charged* price lives on the Stripe Price object;
scripts/stripe_sync.py reconciles the two (lookup keys community_<plan>)."""

import enum
from dataclasses import dataclass


class CommunityPlan(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


@dataclass(frozen=True)
class CommunityPlanSpec:
    plan: CommunityPlan
    name: str
    price_cents: int
    # Stripe recurring interval: "month" | "year"
    interval: str


COMMUNITY_PLANS: dict[CommunityPlan, CommunityPlanSpec] = {
    CommunityPlan.MONTHLY: CommunityPlanSpec(
        plan=CommunityPlan.MONTHLY,
        name="Premium monthly",
        price_cents=900,
        interval="month",
    ),
    CommunityPlan.ANNUAL: CommunityPlanSpec(
        plan=CommunityPlan.ANNUAL,
        name="Premium annual",
        price_cents=9000,
        interval="year",
    ),
}
