"""HTTP validation and serialization for entitlement snapshots and overrides."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.billing.domain import Plan
from app.domains.entitlements.domain import EntitlementKey


class OverrideUpdate(BaseModel):
    limit_value: int | None = Field(ge=0)
    expires_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("expires_at")
    @classmethod
    def future_aware_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Expiry must include a timezone.")
            if value <= datetime.now(UTC):
                raise ValueError("Expiry must be in the future.")
        return value


class EntitlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: EntitlementKey
    limit: int | None
    used: int
    included: bool
    source: Literal["plan", "override"]
    expires_at: datetime | None


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: Plan
    entitlements: list[EntitlementOut]


class OverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: EntitlementKey
    limit_value: int | None
    note: str | None
    expires_at: datetime | None
    created_by_id: uuid.UUID | None
    updated_at: datetime


class AdminSnapshotOut(SnapshotOut):
    overrides: list[OverrideOut]
