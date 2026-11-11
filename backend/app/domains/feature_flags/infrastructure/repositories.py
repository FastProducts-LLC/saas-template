"""Feature-flag SQLAlchemy repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.feature_flags.infrastructure.orm  # noqa: F401
from app.domains.feature_flags.domain.entities import FeatureFlag


class SqlAlchemyFeatureFlagRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, key: str) -> FeatureFlag | None:
        return (
            await self.db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
        ).scalar_one_or_none()

    async def list_all(self) -> list[FeatureFlag]:
        return list((await self.db.execute(select(FeatureFlag))).scalars())

    async def add(self, flag: FeatureFlag) -> None:
        self.db.add(flag)
        await self.db.flush()
