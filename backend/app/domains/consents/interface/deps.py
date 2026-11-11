"""Consents composition root."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.consents.application import use_cases as uc
from app.domains.consents.infrastructure.repositories import (
    SqlAlchemyConsentEventRepository,
)

DB = Annotated[AsyncSession, Depends(get_db)]


def get_record_consent(db: DB) -> uc.RecordConsent:
    return uc.RecordConsent(SqlAlchemyConsentEventRepository(db))


def get_current_consent(db: DB) -> uc.GetCurrentConsent:
    return uc.GetCurrentConsent(SqlAlchemyConsentEventRepository(db))
