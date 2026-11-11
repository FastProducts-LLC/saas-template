"""Feature-flag HTTP schemas — Pydantic at the edge only."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domains.feature_flags.domain.entities import FeatureFlag


class PublicConfigOut(BaseModel):
    """Unauthenticated client bootstrap — flags only, never secrets or
    per-user data."""

    features: dict[str, bool]


class FeatureFlagSet(BaseModel):
    enabled: bool


class AdminFeatureFlagOut(BaseModel):
    key: str
    enabled: bool
    # None when the flag has never been toggled (KNOWN_FLAGS default applies).
    updated_by: uuid.UUID | None
    updated_at: datetime | None

    @classmethod
    def from_state(cls, key: str, enabled: bool, row: FeatureFlag | None) -> "AdminFeatureFlagOut":
        return cls(
            key=key,
            enabled=enabled,
            updated_by=row.updated_by if row else None,
            updated_at=row.updated_at if row else None,
        )


class AdminFeatureFlagList(BaseModel):
    items: list[AdminFeatureFlagOut]
