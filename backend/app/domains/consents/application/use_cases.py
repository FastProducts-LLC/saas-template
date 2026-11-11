"""Consent use cases — append a decision, read back the latest one."""

import logging
import uuid

from app.domains.consents.application.ports import ConsentEventRepository
from app.domains.consents.domain import ConsentEvent

logger = logging.getLogger(__name__)


class RecordConsent:
    """Append an immutable consent decision for a signed-in user."""

    def __init__(self, events: ConsentEventRepository) -> None:
        self.events = events

    async def execute(
        self,
        *,
        user_id: uuid.UUID,
        analytics: bool,
        policy_version: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ConsentEvent:
        event = ConsentEvent(
            user_id=user_id,
            categories={"analytics": analytics},
            policy_version=policy_version.strip()[:32],
            ip_address=ip_address,
            user_agent=(user_agent or "").strip()[:255] or None,
        )
        await self.events.add(event)
        logger.info(
            "consent.recorded user=%s analytics=%s version=%s",
            user_id,
            analytics,
            event.policy_version,
        )
        return event


class GetCurrentConsent:
    """Latest recorded decision for a user, or None if they never decided."""

    def __init__(self, events: ConsentEventRepository) -> None:
        self.events = events

    async def execute(self, *, user_id: uuid.UUID) -> ConsentEvent | None:
        return await self.events.latest_for_user(user_id)
