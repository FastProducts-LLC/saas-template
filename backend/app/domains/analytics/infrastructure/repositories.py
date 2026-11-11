"""SQLAlchemy repository for activity events."""

import logging
import uuid
from datetime import datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.auth.infrastructure.orm  # noqa: F401  (User mapping for the opt-out read)
from app.domains.analytics.domain import ActivityEvent
from app.domains.analytics.infrastructure.orm import activity_events_table
from app.domains.auth.domain import User

logger = logging.getLogger(__name__)


class SqlAlchemyActivityEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, event: ActivityEvent) -> None:
        """Insert inside a SAVEPOINT on the caller's transaction.

        The event commits or rolls back with the surrounding business change,
        but an insert failure (FK race with an account deletion, a bad value)
        only unwinds the savepoint — the request/webhook/worker carries on.

        Pending business writes are flushed FIRST, outside the guarded block,
        so a genuine error in them still propagates instead of being mistaken
        for an analytics failure and swallowed.
        """
        await self.db.flush()
        try:
            async with self.db.begin_nested():
                await self.db.execute(
                    insert(activity_events_table).values(
                        user_id=event.user_id,
                        event=event.event,
                        source=event.source,
                        properties=event.properties,
                        created_at=event.created_at,
                    )
                )
        except Exception:
            logger.exception("activity event write failed: event=%s", event.event)

    async def is_opted_out(self, user_id: uuid.UUID) -> bool:
        await self.db.flush()  # same reasoning as add(): business errors propagate
        try:
            async with self.db.begin_nested():
                opted_out = await self.db.scalar(
                    select(User.analytics_opt_out).where(User.id == user_id)
                )
        except Exception:
            logger.exception("analytics opt-out lookup failed; dropping event")
            return True
        return True if opted_out is None else bool(opted_out)

    async def delete_batch_older_than(self, cutoff: datetime, limit: int) -> int:
        doomed = (
            select(activity_events_table.c.id)
            .where(activity_events_table.c.created_at < cutoff)
            .limit(limit)
        )
        result = await self.db.execute(
            delete(activity_events_table).where(activity_events_table.c.id.in_(doomed))
        )
        return result.rowcount or 0
