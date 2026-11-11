"""Uploaded file metadata and confirmation state."""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class StoredFileStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"


class FilePurpose(str, enum.Enum):
    AVATAR = "avatar"


@dataclass(eq=False)
class StoredFile:
    key: str
    purpose: FilePurpose
    content_type: str
    created_by_id: uuid.UUID
    organization_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    size_bytes: int | None = None
    status: StoredFileStatus = StoredFileStatus.PENDING
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.organization_id is None and self.user_id is None:
            raise ValueError("Stored files must have an organization or user owner")

    def confirm(self, *, size_bytes: int) -> None:
        self.status = StoredFileStatus.READY
        self.size_bytes = size_bytes
        self.confirmed_at = _utcnow()

    @property
    def is_ready(self) -> bool:
        return self.status == StoredFileStatus.READY
