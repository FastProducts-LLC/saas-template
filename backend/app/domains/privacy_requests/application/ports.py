"""Ports for the privacy-requests slice."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.domains.privacy_requests.domain import PrivacyRequest
from app.domains.privacy_requests.domain.entities import PrivacyRequestStatus


class PrivacyRequestRepository(Protocol):
    async def add(self, request: PrivacyRequest) -> None: ...

    async def get(self, request_id: uuid.UUID) -> PrivacyRequest | None: ...

    # Named list_requests (not `list`) so the method does not shadow the builtin
    # when annotations are evaluated without `from __future__ import annotations`.
    async def list_requests(
        self,
        *,
        status: PrivacyRequestStatus | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[PrivacyRequest], int]: ...

    async def list_payload_purge_candidates(self, older_than: datetime) -> list[PrivacyRequest]: ...
