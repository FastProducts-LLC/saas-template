"""Feature-flag composition root + the reusable feature gate."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.feature_flags.application import use_cases as uc
from app.domains.feature_flags.domain.errors import FeatureDisabled
from app.domains.feature_flags.infrastructure.repositories import (
    SqlAlchemyFeatureFlagRepository,
)

DB = Annotated[AsyncSession, Depends(get_db)]


def get_public_config(db: DB) -> uc.GetPublicConfig:
    return uc.GetPublicConfig(SqlAlchemyFeatureFlagRepository(db))


def get_list_feature_flags(db: DB) -> uc.ListFeatureFlags:
    return uc.ListFeatureFlags(SqlAlchemyFeatureFlagRepository(db))


def get_set_feature_flag(db: DB) -> uc.SetFeatureFlag:
    return uc.SetFeatureFlag(SqlAlchemyFeatureFlagRepository(db))


def require_feature(key: str):
    """Router/route dependency that 404s every request while `key` is off.

    Single-row read per request — cheap enough for MVP; add a short TTL
    cache here if flag reads ever show up in profiles.
    """

    async def _dep(db: DB) -> None:
        flags = await uc.GetPublicConfig(SqlAlchemyFeatureFlagRepository(db)).execute()
        if not flags.get(key):
            raise FeatureDisabled(f"Feature '{key}' is not enabled.")

    return Depends(_dep)
