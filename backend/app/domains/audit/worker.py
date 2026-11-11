"""Audit background jobs — the composition root (no request context)."""

import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.domains.audit.application.use_cases import PurgeExpiredAuditEvents
from app.domains.audit.infrastructure.repositories import SqlAlchemyAuditEventRepository

logger = logging.getLogger(__name__)


async def purge_expired_audit_events() -> int:
    """Delete audit events past retention; returns rows removed."""
    async with SessionLocal() as session:
        async with session.begin():
            use_case = PurgeExpiredAuditEvents(
                SqlAlchemyAuditEventRepository(session), settings.audit_retention_days
            )
            deleted = await use_case.execute()
    if deleted:
        logger.info("Purged %d expired audit event(s)", deleted)
    return deleted
