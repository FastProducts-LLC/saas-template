"""API key application ports — interfaces consumed by use cases."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.domains.api_keys.domain.entities import ApiKey
from app.domains.entitlements.domain import EntitlementKey


class ApiKeyRepository(Protocol):
    async def count_active(self, org_id: uuid.UUID) -> int: ...

    async def add(self, key: ApiKey) -> None: ...
    async def get(self, org_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None: ...
    async def get_by_hash(self, key_hash: str) -> ApiKey | None: ...
    async def list_active(self, org_id: uuid.UUID) -> list[ApiKey]: ...


class EntitlementChecker(Protocol):
    async def ensure_within_limit(
        self, org_id: uuid.UUID, key: EntitlementKey, count: Callable[[], Awaitable[int]]
    ) -> None: ...
