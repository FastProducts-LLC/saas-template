"""Billing API schemas."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.domains.billing.domain.value_objects import BillingInterval, Plan, PlanSubscriptionStatus
from app.domains.credits.domain import CreditPack


class BillingAccountOut(BaseModel):
    has_billing_account: bool


class InvoiceOut(BaseModel):
    id: str
    number: str | None
    status: str
    amount_due: int
    currency: str
    created: datetime
    hosted_invoice_url: str | None
    invoice_pdf: str | None


class CreditPackOut(BaseModel):
    pack: CreditPack
    name: str
    credits: int
    price_cents: int
    unit_price_cents: int
    discount_pct: int
    purchasable: bool


class CreditPackCheckoutRequest(BaseModel):
    pack: CreditPack


class RedirectResponse(BaseModel):
    url: str


class PlanPurchasable(BaseModel):
    monthly: bool
    annual: bool


class PlanOut(BaseModel):
    plan: Plan
    name: str
    monthly_price_cents: int
    annual_price_cents: int
    monthly_credits: int
    purchasable: PlanPurchasable


class PlanCheckoutRequest(BaseModel):
    plan: Plan
    interval: BillingInterval

    @field_validator("plan")
    @classmethod
    def paid_plan(cls, value: Plan) -> Plan:
        if value == Plan.FREE:
            raise ValueError("The free plan is not purchasable.")
        return value


class SubscriptionOut(BaseModel):
    plan: Plan
    interval: BillingInterval
    status: PlanSubscriptionStatus
    current_period_end: datetime | None
    cancel_at_period_end: bool


class BillingPlanOut(BaseModel):
    plan: Plan
    subscription: SubscriptionOut | None
