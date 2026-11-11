"""Generations repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.generations.infrastructure.orm  # noqa: F401
from app.domains.generations.domain import Generation


class SqlAlchemyGenerationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, generation_id: uuid.UUID) -> Generation | None:
        return await self.db.get(Generation, generation_id)

    async def get_for_org(self, org_id: uuid.UUID, generation_id: uuid.UUID) -> Generation | None:
        stmt = select(Generation).where(
            Generation.id == generation_id, Generation.organization_id == org_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, org_id: uuid.UUID, limit: int, offset: int) -> list[Generation]:
        stmt = (
            select(Generation)
            .where(Generation.organization_id == org_id)
            .order_by(Generation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars())

    async def add(self, generation: Generation) -> None:
        self.db.add(generation)
        await self.db.flush()

    async def remove(self, generation: Generation) -> None:
        await self.db.delete(generation)
        await self.db.flush()
