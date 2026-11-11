"""Ports for the audit slice."""

import uuid
from datetime import datetime
from typing import Protocol

from app.domains.audit.domain import AuditEvent


class AuditEventRepository(Protocol):
    async def add(self, event: AuditEvent) -> None: ...

    async def list_events(
        self,
        *,
        action: str | None,
        actor_user_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[AuditEvent, str | None]], int]:
        """Newest first; each row pairs the event with the actor's email (if any)."""
        ...

    async def delete_older_than(self, cutoff: datetime) -> int: ...
