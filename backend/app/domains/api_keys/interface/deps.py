"""API keys composition root — the ONLY place use cases meet concrete adapters."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.api_keys.application import use_cases as uc
from app.domains.api_keys.infrastructure.repositories import SqlAlchemyApiKeyRepository

DB = Annotated[AsyncSession, Depends(get_db)]


def get_create_api_key(db: DB) -> uc.CreateApiKey:
    from app.domains.entitlements.interface.deps import build_entitlement_service

    return uc.CreateApiKey(
        SqlAlchemyApiKeyRepository(db), entitlements=build_entitlement_service(db)
    )


def get_list_api_keys(db: DB) -> uc.ListApiKeys:
    return uc.ListApiKeys(SqlAlchemyApiKeyRepository(db))


def get_revoke_api_key(db: DB) -> uc.RevokeApiKey:
    return uc.RevokeApiKey(SqlAlchemyApiKeyRepository(db))


def build_api_key_counter(db: AsyncSession) -> SqlAlchemyApiKeyRepository:
    """Export the organization's non-revoked API-key count to other slices."""
    return SqlAlchemyApiKeyRepository(db)
