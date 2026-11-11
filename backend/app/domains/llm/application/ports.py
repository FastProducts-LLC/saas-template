"""LLM application ports."""

import uuid
from typing import Any, Protocol

from app.domains.credits.domain import CreditAction
from app.domains.llm.domain.entities import LlmCall, LlmProvider, LlmResult


class LlmGateway(Protocol):
    """The text LLM providers, behind one dispatching port."""

    def check_configured(self, provider: LlmProvider) -> None:
        """Fail fast (before holding credits) when the provider key is missing.
        Raises LlmProviderNotConfigured."""
        ...

    def model_for(self, provider: LlmProvider) -> str: ...

    async def complete(self, provider: LlmProvider, prompt: str, max_tokens: int) -> LlmResult: ...


class LlmCallRepository(Protocol):
    async def add(self, call: LlmCall) -> None: ...

    async def get(self, call_id: uuid.UUID) -> LlmCall | None: ...

    async def get_for_org(self, org_id: uuid.UUID, call_id: uuid.UUID) -> LlmCall | None: ...

    async def list_for_org(self, org_id: uuid.UUID, limit: int, offset: int) -> list[LlmCall]: ...


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
