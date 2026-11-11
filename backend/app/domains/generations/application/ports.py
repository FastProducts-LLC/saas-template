"""Generations application ports."""

import uuid
from typing import Any, Protocol

from app.domains.credits.domain import CreditAction
from app.domains.generations.application.dtos import MediaDownload, MediaFileUrl
from app.domains.generations.domain import GeneratedAsset, Generation


class GenerationRepository(Protocol):
    async def get(self, generation_id: uuid.UUID) -> Generation | None: ...

    async def get_for_org(
        self, org_id: uuid.UUID, generation_id: uuid.UUID
    ) -> Generation | None: ...

    async def list_for_org(
        self, org_id: uuid.UUID, limit: int, offset: int
    ) -> list[Generation]: ...

    async def add(self, generation: Generation) -> None: ...

    async def remove(self, generation: Generation) -> None: ...


class ProviderGateway(Protocol):
    """The AI providers, behind one dispatching port."""

    def check_configured(self, kind: CreditAction) -> None:
        """Fail fast (before holding credits) when the provider key is missing.
        Raises ProviderNotConfigured."""
        ...

    def model_for(self, kind: CreditAction) -> str: ...

    async def run(self, kind: CreditAction, prompt: str) -> GeneratedAsset: ...


class MediaStore(Protocol):
    async def save(self, org_id: uuid.UUID, name: str, asset: GeneratedAsset) -> str:
        """Persist the asset and return its storage key."""
        ...

    def extension_for(self, mime_type: str) -> str: ...

    async def download(self, file_path: str, mime_type: str) -> MediaDownload: ...

    async def file_url(self, file_path: str) -> MediaFileUrl: ...

    async def delete(self, file_path: str) -> None:
        """Remove a stored asset by its key; the use case handles failures."""
        ...


class CreditService(Protocol):
    """The slice of the credits engine this domain needs (structurally
    satisfied by `credits.application.use_cases.CreditEngine`)."""

    async def reserve(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None,
        action: CreditAction,
        reference: str | None = None,
    ) -> Any: ...

    async def capture(self, reservation_id: uuid.UUID) -> Any: ...

    async def release(self, reservation_id: uuid.UUID, reason: str | None = None) -> Any: ...


class ActivityTracker(Protocol):
    """Product-analytics server events — satisfied structurally by the
    analytics slice's CaptureServerEvent (cross-slice port idiom). Writes are
    best-effort, never raise, and skip silently when `user_id` is None or the
    user opted out. Event names come from shared/events.toml."""

    async def capture_server_event(
        self, user_id: "uuid.UUID | None", event: str, properties: dict | None = None
    ) -> object: ...
