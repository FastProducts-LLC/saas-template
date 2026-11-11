"""Framework-independent entitlement snapshots."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domains.billing.domain import Plan
from app.domains.entitlements.domain import EntitlementKey


@dataclass(frozen=True)
class EntitlementUsage:
    key: EntitlementKey
    limit: int | None
    used: int
    included: bool
    source: Literal["plan", "override"]
    expires_at: datetime | None


@dataclass(frozen=True)
class EntitlementSnapshot:
    plan: Plan
    entitlements: list[EntitlementUsage]
