"""Emails infrastructure: webhook event log persistence.

(Marketing/suppression flags live on the auth-owned `users` table; that
writer is auth's `SqlAlchemyMarketingPreferencesRepository`, consumed via
`build_marketing_preferences_repository` in emails' composition root.)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.emails.infrastructure.orm  # noqa: F401
from app.domains.emails.domain import EmailEvent


class SqlAlchemyEmailEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def seen(self, svix_id: str) -> bool:
        stmt = select(EmailEvent.id).where(EmailEvent.svix_id == svix_id).limit(1)
        return (await self.db.execute(stmt)).first() is not None

    async def add(self, event: EmailEvent) -> None:
        self.db.add(event)
        # Surface a duplicate-svix_id violation here (a redelivery racing the
        # seen() check) instead of at end-of-request commit; the resulting 5xx
        # makes Svix retry, and the retry then short-circuits on seen().
        await self.db.flush()
