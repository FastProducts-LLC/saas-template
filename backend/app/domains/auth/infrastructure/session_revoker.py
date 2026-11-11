"""Autonomous session revoker (SessionRevoker port).

Refresh-token reuse detection revokes every session and then raises
SessionExpired — which rolls back the request transaction. The revocation
therefore commits in its own short-lived session, the same pattern as
`audit.infrastructure.recorder.AutonomousAuditRecorder`.

Unlike the audit recorder this is NOT best-effort: a failure propagates (the
request fails with a 500 instead of a 401) rather than silently leaving a
suspected-stolen chain alive.
"""

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domains.auth.infrastructure.repositories import SqlAlchemyRefreshTokenRepository


class AutonomousSessionRevoker:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await SqlAlchemyRefreshTokenRepository(session).revoke_all_for_user(user_id)
