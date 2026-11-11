"""Analytics use cases.

Every write path is best-effort by contract: a dropped analytics event is
acceptable, an analytics failure surfacing in a login, webhook, or worker is
not. Callers get a bool ("was it recorded") purely for tests and debug logs.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.domains.analytics.application.ports import ActivityEventRepository, IngestRateGate
from app.domains.analytics.domain import CLIENT_EVENTS, SERVER_EVENTS, ActivityEvent
from app.domains.analytics.domain.entities import SOURCE_CLIENT, SOURCE_SERVER
from app.domains.analytics.domain.policy import sanitize_properties

logger = logging.getLogger(__name__)

PURGE_BATCH_SIZE = 10_000


class RecordClientEvent:
    """Browser-originated event from POST /api/events.

    The user comes from the session, never the payload. Only CLIENT_EVENTS
    are accepted, so a browser cannot forge server-truth names (purchases,
    activation) into the table.
    """

    def __init__(self, events: ActivityEventRepository, gate: IngestRateGate) -> None:
        self.events = events
        self.gate = gate

    async def execute(
        self, *, user_id: uuid.UUID, opted_out: bool, event: object, properties: object
    ) -> bool:
        if opted_out:
            return False
        if not isinstance(event, str) or event not in CLIENT_EVENTS:
            logger.debug("analytics ingest dropped: unknown event %r", event)
            return False
        clean = sanitize_properties(properties)
        if clean is None:
            logger.debug("analytics ingest dropped: non-object properties for %s", event)
            return False
        if not await self.gate.allow(user_id):
            logger.debug("analytics ingest dropped: rate limit for user %s", user_id)
            return False
        await self.events.add(
            ActivityEvent(user_id=user_id, event=event, source=SOURCE_CLIENT, properties=clean)
        )
        return True


class CaptureServerEvent:
    """Server-truth event, written where the fact is established (webhook,
    worker, use case) inside the caller's transaction — so it commits or
    rolls back together with the business change it describes.

    Other slices depend on this through their own minimal `ActivityTracker`
    Protocol (cross-slice port idiom), built via
    `analytics.interface.deps.build_activity_tracker`.
    """

    def __init__(self, events: ActivityEventRepository) -> None:
        self.events = events

    async def capture_server_event(
        self, user_id: uuid.UUID | None, event: str, properties: dict | None = None
    ) -> bool:
        if user_id is None:
            return False  # API-key / system actors: no user to attribute to
        if event not in SERVER_EVENTS:
            # A typo or an unregistered name — loud in logs, never raised.
            logger.error("analytics: %r is not a registered server event", event)
            return False
        if await self.events.is_opted_out(user_id):
            return False
        await self.events.add(
            ActivityEvent(
                user_id=user_id,
                event=event,
                source=SOURCE_SERVER,
                properties=sanitize_properties(properties) or {},
            )
        )
        return True


class PurgeExpiredActivityEvents:
    """Retention purge. One bounded batch per call so a delete never holds a
    long lock; the worker loops, one transaction per batch."""

    def __init__(self, events: ActivityEventRepository, retention_days: int) -> None:
        self.events = events
        self.retention_days = retention_days

    async def execute(self, *, batch_size: int = PURGE_BATCH_SIZE) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        return await self.events.delete_batch_older_than(cutoff, batch_size)
