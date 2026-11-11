"""Pure entitlement resolution and capacity checks."""

from datetime import datetime

from app.domains.billing.domain import Plan
from app.domains.entitlements.domain.entities import (
    PLAN_ENTITLEMENTS,
    EntitlementKey,
    EntitlementOverride,
)


def resolve_limit(
    plan: Plan,
    key: EntitlementKey,
    override: EntitlementOverride | None,
    *,
    now: datetime | None = None,
) -> int | None:
    if override is not None and override.is_active(now):
        return override.limit_value
    return PLAN_ENTITLEMENTS[plan][key]


def is_included(limit: int | None) -> bool:
    return limit != 0


def within_limit(limit: int | None, current_count: int) -> bool:
    return limit is None or current_count < limit
