"""Emails composition root — the only place emails use cases meet adapters."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.interface.deps import build_marketing_preferences_repository
from app.domains.emails.application.use_cases import ProcessResendEvent
from app.domains.emails.infrastructure.repositories import SqlAlchemyEmailEventRepository
from app.domains.emails.infrastructure.webhooks import ResendWebhookVerifier

DB = Annotated[AsyncSession, Depends(get_db)]

_verifier = ResendWebhookVerifier()


def get_process_resend_event(db: DB) -> ProcessResendEvent:
    # Auth owns the users table; its marketing-preferences writer satisfies
    # emails' MarketingPreferencesRepository port structurally.
    return ProcessResendEvent(
        build_marketing_preferences_repository(db), SqlAlchemyEmailEventRepository(db)
    )


def get_webhook_verifier() -> ResendWebhookVerifier:
    return _verifier
