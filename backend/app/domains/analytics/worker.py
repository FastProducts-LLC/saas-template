"""Analytics background jobs — the composition root (no request context)."""

import logging

from app.core.database import SessionLocal
from app.core.policy import ACTIVITY_EVENT_RETENTION_DAYS
from app.domains.analytics.application.use_cases import PurgeExpiredActivityEvents
from app.domains.analytics.infrastructure.repositories import SqlAlchemyActivityEventRepository

logger = logging.getLogger(__name__)

# Safety valve: 500 batches x 10k rows per run. A backlog larger than that
# simply continues on the next scheduled run.
MAX_BATCHES_PER_RUN = 500


async def purge_expired_activity_events(session_factory=SessionLocal) -> int:
    """Delete activity events past retention in bounded batches, one
    transaction per batch; returns total rows removed."""
    total = 0
    for _ in range(MAX_BATCHES_PER_RUN):
        async with session_factory() as session:
            async with session.begin():
                deleted = await PurgeExpiredActivityEvents(
                    SqlAlchemyActivityEventRepository(session), ACTIVITY_EVENT_RETENTION_DAYS
                ).execute()
        total += deleted
        if deleted == 0:
            break
    if total:
        logger.info("Purged %d expired activity event(s)", total)
    return total
