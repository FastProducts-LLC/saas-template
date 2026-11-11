"""Ports for the analytics slice."""

import uuid
from datetime import datetime
from typing import Protocol

from app.domains.analytics.domain import ActivityEvent


class ActivityEventRepository(Protocol):
    async def add(self, event: ActivityEvent) -> None:
        """Persist one event. Must never poison the caller's transaction."""
        ...

    async def is_opted_out(self, user_id: uuid.UUID) -> bool:
        """True when the user objected to analytics, no longer exists, or the
        lookup failed (unknown = don't record). Must not raise."""
        ...

    async def delete_batch_older_than(self, cutoff: datetime, limit: int) -> int:
        """Delete up to `limit` rows older than `cutoff`; returns rows removed."""
        ...


class IngestRateGate(Protocol):
    """Per-user ingest throttle. Fail-open: analytics never blocks on Redis."""

    async def allow(self, user_id: uuid.UUID) -> bool: ...
