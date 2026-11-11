"""API key SQLAlchemy repository."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.api_keys.infrastructure.orm  # noqa: F401
from app.domains.api_keys.domain.entities import ApiKey


class SqlAlchemyApiKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, key: ApiKey) -> None:
        self.db.add(key)
        await self.db.flush()

    async def get(self, org_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None:
        return (
            await self.db.execute(
                select(ApiKey).where(ApiKey.organization_id == org_id, ApiKey.id == key_id)
            )
        ).scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        return (
            await self.db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
        ).scalar_one_or_none()

    async def list_active(self, org_id: uuid.UUID) -> list[ApiKey]:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.organization_id == org_id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_active(self, org_id: uuid.UUID) -> int:
        return (
            await self.db.execute(
                select(func.count())
                .select_from(ApiKey)
                .where(
                    ApiKey.organization_id == org_id,
                    ApiKey.revoked_at.is_(None),
                )
            )
        ).scalar_one()
