"""Audit domain entities.

Security-relevant event trail (logins, password changes, purchases) — distinct
from admin_audit_log, which records only platform-admin mutations and feeds the
admin analytics widget. Append-only by convention: the repository exposes
add/list/purge only.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class AuditEvent:
    action: str  # canonical constants in domain/actions.py, e.g. "auth.login_failed"
    # Nullable: failed logins on unknown emails and webhook-driven billing
    # events have no authenticated actor.
    actor_user_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None
    target_type: str | None = None
    target_id: uuid.UUID | None = None
    ip: str | None = None
    user_agent: str | None = None
    # Action-specific context. Named `meta` because `metadata` is reserved on
    # SQLAlchemy-mapped classes. May contain PII (e.g. the attempted email on
    # login failures) — superuser-only reads, bounded by the retention purge.
    meta: dict = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
