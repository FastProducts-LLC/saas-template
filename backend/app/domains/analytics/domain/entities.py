"""Analytics domain entities — pure Python.

`ActivityEvent` is one row of the first-party product-analytics log: what a
signed-in user did (client events) or what verifiably happened for them
(server events). It is NOT the security trail — that is `audit_events`, which
may hold PII and has its own retention.

Contract: the table is `activity_events` and the `user_id` / `created_at`
columns are read by external DAU/retention queries. Add fields freely; never
rename those.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

SOURCE_CLIENT = "client"
SOURCE_SERVER = "server"


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class ActivityEvent:
    # Always a real users.id — anonymous activity is never recorded here.
    user_id: uuid.UUID
    event: str  # a name from shared/events.toml
    # Client claim vs server truth; impossible to backfill, so always set.
    source: str = SOURCE_CLIENT
    # Identifiers, enums, and numbers only (see domain/policy.py).
    properties: dict = field(default_factory=dict)
    id: int | None = None  # database identity
    created_at: datetime = field(default_factory=_utcnow)
