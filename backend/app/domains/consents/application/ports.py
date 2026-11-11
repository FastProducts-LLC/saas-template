"""Ports for the consents slice."""

import uuid
from typing import Protocol

from app.domains.consents.domain import ConsentEvent


class ConsentEventRepository(Protocol):
    async def add(self, event: ConsentEvent) -> None: ...

    async def latest_for_user(self, user_id: uuid.UUID) -> ConsentEvent | None: ...
