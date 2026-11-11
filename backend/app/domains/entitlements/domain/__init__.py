"""Entitlements domain public surface."""

from app.domains.entitlements.domain.entities import (
    PLAN_ENTITLEMENTS,
    EntitlementKey,
    EntitlementOverride,
)
from app.domains.entitlements.domain.errors import (
    EntitlementLimitReached,
    EntitlementRequired,
    UnknownEntitlementKey,
)
from app.domains.entitlements.domain.policy import (
    is_included,
    resolve_limit,
    within_limit,
)

__all__ = [
    "PLAN_ENTITLEMENTS",
    "EntitlementKey",
    "EntitlementOverride",
    "EntitlementRequired",
    "EntitlementLimitReached",
    "UnknownEntitlementKey",
    "resolve_limit",
    "is_included",
    "within_limit",
]
