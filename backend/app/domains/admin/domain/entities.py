"""Admin domain entities.

The audit log is append-only by convention: the repository exposes add/list
only, and entries are flushed in the same transaction as the mutation they
describe, so a logged action and its audit row are atomic.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class AdminAuditEntry:
    action: str  # e.g. "user.deactivate", "org.suspend", "credits.adjust"
    target_type: str  # "user" | "organization" | "invitation"
    actor_user_id: uuid.UUID | None = None
    target_id: uuid.UUID | None = None
    # Action-specific context (amounts, descriptions, ...). Named `meta`
    # because `metadata` is reserved on SQLAlchemy-mapped classes.
    meta: dict = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
