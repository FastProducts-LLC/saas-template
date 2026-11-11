"""HTTP representations of the revenue read model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.billing.domain.value_objects import BillingInterval, Plan


class PlanRevenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: Plan
    interval: BillingInterval
    count: int
    mrr_cents: int


class RevenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    mrr_cents: int
    arr_cents: int
    active: int
    trialing: int
    past_due: int
    canceling: int
    by_plan: list[PlanRevenueOut] = Field(
        description=(
            "Live subscription counts by paid plan and interval. MRR entries round independently; "
            "their sum may differ from the exact-total rounded mrr_cents by a cent."
        )
    )
    new_last_30d: int
    canceled_last_30d: int
    computed_at: datetime
