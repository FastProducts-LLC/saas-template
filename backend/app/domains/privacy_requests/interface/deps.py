"""Privacy-requests composition root."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.privacy_requests.application import use_cases as uc
from app.domains.privacy_requests.infrastructure.repositories import (
    SqlAlchemyPrivacyRequestRepository,
)

DB = Annotated[AsyncSession, Depends(get_db)]


def get_privacy_request_repo(db: DB) -> SqlAlchemyPrivacyRequestRepository:
    return SqlAlchemyPrivacyRequestRepository(db)


def get_submit_privacy_request(db: DB) -> uc.SubmitPrivacyRequest:
    return uc.SubmitPrivacyRequest(SqlAlchemyPrivacyRequestRepository(db))


def get_verify_privacy_request(db: DB) -> uc.VerifyPrivacyRequest:
    return uc.VerifyPrivacyRequest(SqlAlchemyPrivacyRequestRepository(db))


def get_forward_privacy_request(db: DB) -> uc.ForwardPrivacyRequest:
    return uc.ForwardPrivacyRequest(SqlAlchemyPrivacyRequestRepository(db))


def get_fulfill_privacy_request(db: DB) -> uc.FulfillPrivacyRequest:
    return uc.FulfillPrivacyRequest(SqlAlchemyPrivacyRequestRepository(db))


def get_close_privacy_request(db: DB) -> uc.ClosePrivacyRequest:
    return uc.ClosePrivacyRequest(SqlAlchemyPrivacyRequestRepository(db))


def get_reject_privacy_request(db: DB) -> uc.RejectPrivacyRequest:
    return uc.RejectPrivacyRequest(SqlAlchemyPrivacyRequestRepository(db))
