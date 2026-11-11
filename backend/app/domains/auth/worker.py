"""Auth background jobs — the composition root (no request context)."""

import logging

from app.core.database import SessionLocal
from app.domains.auth.application.use_cases import PurgeExpiredRefreshTokens
from app.domains.auth.infrastructure.repositories import SqlAlchemyRefreshTokenRepository

logger = logging.getLogger(__name__)


async def purge_expired_refresh_tokens() -> int:
    """Delete long-dead refresh tokens; returns rows removed."""
    async with SessionLocal() as session:
        async with session.begin():
            use_case = PurgeExpiredRefreshTokens(SqlAlchemyRefreshTokenRepository(session))
            deleted = await use_case.execute()
    if deleted:
        logger.info("Purged %d expired refresh token(s)", deleted)
    return deleted
