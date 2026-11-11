"""LLM call repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.llm.infrastructure.orm  # noqa: F401
from app.domains.llm.domain.entities import LlmCall


class SqlAlchemyLlmCallRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, call: LlmCall) -> None:
        self.db.add(call)
        await self.db.flush()

    async def get(self, call_id: uuid.UUID) -> LlmCall | None:
        return await self.db.get(LlmCall, call_id)

    async def get_for_org(self, org_id: uuid.UUID, call_id: uuid.UUID) -> LlmCall | None:
        stmt = select(LlmCall).where(LlmCall.id == call_id, LlmCall.organization_id == org_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, org_id: uuid.UUID, limit: int, offset: int) -> list[LlmCall]:
        stmt = (
            select(LlmCall)
            .where(LlmCall.organization_id == org_id)
            .order_by(LlmCall.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars())
