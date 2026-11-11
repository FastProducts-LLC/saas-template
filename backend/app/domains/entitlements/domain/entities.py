"""Plan limits and organization-specific overrides."""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domains.billing.domain import Plan


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EntitlementKey(str, enum.Enum):
    SEATS = "seats"
    API_KEYS = "api_keys"

    @property
    def label(self) -> str:
        """Plural, user-facing noun — fills ERR_ENT_002's `{resource}`."""
        return ENTITLEMENT_LABELS[self]


ENTITLEMENT_LABELS: dict["EntitlementKey", str] = {
    EntitlementKey.SEATS: "seats",
    EntitlementKey.API_KEYS: "API keys",
}


# None means unlimited; zero means the feature is not included.
PLAN_ENTITLEMENTS: dict[Plan, dict[EntitlementKey, int | None]] = {
    Plan.FREE: {EntitlementKey.SEATS: 5, EntitlementKey.API_KEYS: 5},
    Plan.PRO: {EntitlementKey.SEATS: 15, EntitlementKey.API_KEYS: 20},
    Plan.TEAM: {EntitlementKey.SEATS: None, EntitlementKey.API_KEYS: 50},
}


@dataclass(eq=False)
class EntitlementOverride:
    organization_id: uuid.UUID
    key: EntitlementKey
    limit_value: int | None
    source: str = "admin"
    note: str | None = None
    expires_at: datetime | None = None
    created_by_id: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def is_active(self, now: datetime | None = None) -> bool:
        return self.expires_at is None or (now or _utcnow()) < self.expires_at
