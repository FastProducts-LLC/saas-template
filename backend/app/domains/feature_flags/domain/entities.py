"""Feature-flag domain entities — pure Python, zero framework/ORM imports."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Registry of valid flag keys and their defaults. GET /api/config merges DB
# rows over these, so a flag needs no seeding to exist — an absent row means
# the default applies. Add new toggleable modules here.
KNOWN_FLAGS: dict[str, bool] = {
    "community": False,
}


@dataclass(eq=False)
class FeatureFlag:
    """A runtime on/off switch, editable by superusers without a restart."""

    key: str
    enabled: bool
    updated_by: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def set_enabled(self, enabled: bool, *, by: uuid.UUID | None) -> None:
        self.enabled = enabled
        self.updated_by = by
        self.updated_at = _utcnow()
