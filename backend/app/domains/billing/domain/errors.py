"""Billing domain errors."""

from app.core.exceptions import AppError, ConflictError


class BillingNotConfigured(ConflictError):
    code = "billing_not_configured"
    internal_code = "ERR_BILL_001"


class NoBillingAccount(ConflictError):
    code = "no_billing_account"
    internal_code = "ERR_BILL_004"


class StripeUnavailable(AppError):
    """Stripe connection error / 5xx / rate limit — the customer was NOT charged."""

    status_code = 502
    code = "payment_provider_unavailable"
    internal_code = "ERR_BILL_002"


class PackNotPurchasable(ConflictError):
    """A credit pack whose Stripe price id is unset."""

    code = "pack_not_purchasable"
    internal_code = "ERR_BILL_006"


class CommunityPlanNotConfigured(ConflictError):
    """A community membership plan whose Stripe price id is unset."""

    code = "community_plan_not_configured"
    internal_code = "ERR_BILL_007"


class PlanNotConfigured(ConflictError):
    """A paid organization plan whose Stripe price id is unset."""

    code = "plan_not_configured"
    internal_code = "ERR_BILL_008"


class SubscriptionAlreadyActive(ConflictError):
    """An existing live paid subscription must be changed through the portal."""

    code = "subscription_already_active"
    internal_code = "ERR_BILL_009"
