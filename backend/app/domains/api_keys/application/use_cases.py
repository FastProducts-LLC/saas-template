"""API key use cases."""

import hashlib
import secrets
import uuid

from app.core.policy import API_KEY_PREFIX as KEY_PREFIX
from app.domains.api_keys.application.ports import ApiKeyRepository, EntitlementChecker
from app.domains.api_keys.domain.entities import ApiKey
from app.domains.api_keys.domain.errors import ApiKeyNotFound
from app.domains.entitlements.domain import EntitlementKey


def _generate_raw_key() -> str:
    return KEY_PREFIX + secrets.token_hex(32)


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class CreateApiKey:
    def __init__(
        self, repo: ApiKeyRepository, entitlements: EntitlementChecker | None = None
    ) -> None:
        self.repo = repo
        self.entitlements = entitlements

    async def execute(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
    ) -> tuple[ApiKey, str]:
        """Returns (api_key, raw_key). The raw key is shown exactly once."""
        if self.entitlements is not None:
            await self.entitlements.ensure_within_limit(
                org_id, EntitlementKey.API_KEYS, lambda: self.repo.count_active(org_id)
            )
        raw = _generate_raw_key()
        key = ApiKey(
            organization_id=org_id,
            name=name.strip(),
            key_prefix=raw[: len(KEY_PREFIX) + 8],
            key_hash=_hash_key(raw),
            created_by_id=user_id,
        )
        await self.repo.add(key)
        return key, raw


class ListApiKeys:
    def __init__(self, repo: ApiKeyRepository) -> None:
        self.repo = repo

    async def execute(self, org_id: uuid.UUID) -> list[ApiKey]:
        return await self.repo.list_active(org_id)


class RevokeApiKey:
    def __init__(self, repo: ApiKeyRepository) -> None:
        self.repo = repo

    async def execute(self, org_id: uuid.UUID, key_id: uuid.UUID) -> None:
        key = await self.repo.get(org_id, key_id)
        if not key:
            raise ApiKeyNotFound("API key not found.")
        key.revoke()
