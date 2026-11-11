"""Plan feature and capacity errors."""

from app.core.exceptions import AppError, PermissionDeniedError


class EntitlementRequired(PermissionDeniedError):
    code = "entitlement_required"
    internal_code = "ERR_ENT_001"


class EntitlementLimitReached(PermissionDeniedError):
    code = "entitlement_limit_reached"
    internal_code = "ERR_ENT_002"


class UnknownEntitlementKey(AppError):
    status_code = 422
    code = "unknown_entitlement_key"
    internal_code = "ERR_ENT_003"
