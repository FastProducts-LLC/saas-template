"""Privacy retention jobs — purge raw intake payloads after the retention window.

Keeps status, identifier hashes, provider refs, and admin notes for audit.
Idempotent: already-purged rows are skipped.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.domains.privacy_requests.application.use_cases import PurgePrivacyRequestPayloads
from app.domains.privacy_requests.domain.entities import REQUEST_PAYLOAD_RETENTION_DAYS
from app.domains.privacy_requests.infrastructure.repositories import (
    SqlAlchemyPrivacyRequestRepository,
)


async def purge_stale_privacy_payloads(db: AsyncSession | None = None) -> dict[str, int]:
    """Drop raw privacy-request PII past the retention window."""
    if db is not None:
        return await _purge(db)
    async with SessionLocal() as session:
        async with session.begin():
            return await _purge(session)


async def _purge(db: AsyncSession) -> dict[str, int]:
    now = datetime.now(UTC)
    privacy_cutoff = now - timedelta(days=REQUEST_PAYLOAD_RETENTION_DAYS)

    privacy_purged = await PurgePrivacyRequestPayloads(
        SqlAlchemyPrivacyRequestRepository(db)
    ).execute(privacy_cutoff)

    return {"privacy_payloads_purged": privacy_purged}
