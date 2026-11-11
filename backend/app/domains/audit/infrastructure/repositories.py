"""SQLAlchemy repository for audit events."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.audit.infrastructure.orm  # noqa: F401  (attaches the mapping)
import app.domains.auth.infrastructure.orm  # noqa: F401  (User mapping for joins)
from app.domains.audit.domain import AuditEvent
from app.domains.auth.domain import User


class SqlAlchemyAuditEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, event: AuditEvent) -> None:
        self.db.add(event)
        await self.db.flush()

    async def list_events(
        self,
        *,
        action: str | None,
        actor_user_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[AuditEvent, str | None]], int]:
        base = select(AuditEvent)
        if action is not None:
            base = base.where(AuditEvent.action == action)
        if actor_user_id is not None:
            base = base.where(AuditEvent.actor_user_id == actor_user_id)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = (
            base.add_columns(User.email)
            .outerjoin(User, User.id == AuditEvent.actor_user_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(event, email) for event, email in rows], total

    async def delete_older_than(self, cutoff: datetime) -> int:
        result = await self.db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
        return result.rowcount or 0
