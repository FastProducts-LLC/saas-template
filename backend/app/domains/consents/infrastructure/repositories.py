"""Consent-event repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.consents.infrastructure.orm  # noqa: F401
from app.domains.consents.domain import ConsentEvent


class SqlAlchemyConsentEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, event: ConsentEvent) -> None:
        self.db.add(event)
        await self.db.flush()

    async def latest_for_user(self, user_id: uuid.UUID) -> ConsentEvent | None:
        stmt = (
            select(ConsentEvent)
            .where(ConsentEvent.user_id == user_id)
            .order_by(ConsentEvent.created_at.desc(), ConsentEvent.id.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
