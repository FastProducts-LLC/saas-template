"""Autonomous audit recorder.

Each event commits in its own short-lived session, NOT the request
transaction: `auth.login_failed` must survive the rollback that raising
InvalidCredentials triggers, and that's exactly the event an investigation
needs. Trade-off accepted: an event can rarely outlive a later rollback of
the request that produced it.

Best-effort by design — a broken audit store must never take down login or
billing, so failures log loudly and are swallowed (same stance as
app.core.email).
"""

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

import app.domains.audit.infrastructure.orm  # noqa: F401  (attaches the mapping)
from app.domains.audit.domain import AuditEvent

logger = logging.getLogger(__name__)


class AutonomousAuditRecorder:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def record(self, event: AuditEvent) -> None:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(event)
        except Exception:
            logger.exception("audit event write failed: action=%s", event.action)
