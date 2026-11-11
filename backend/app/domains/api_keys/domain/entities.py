"""API key domain entities — pure Python, zero framework/ORM imports."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class ApiKey:
    organization_id: uuid.UUID
    name: str
    key_prefix: str
    key_hash: str
    created_by_id: uuid.UUID
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = _utcnow()

    def touch(self) -> None:
        self.last_used_at = _utcnow()
