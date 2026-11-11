"""LLM domain: metered text completions in front of Gemini / OpenAI / Anthropic.

A completion is a two-phase flow (like generations): credits are reserved in
the request transaction, the provider call runs in a Celery worker, and the
result is persisted + the hold settled in a fresh transaction. The full
response text is stored in ``response_text``; ``response_preview`` is a
bounded excerpt for list/audit views.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Persisted response preview cap — list/audit views show only this many chars.
RESPONSE_PREVIEW_CHARS = 8_000


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LlmProvider(str, enum.Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LlmCallStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class LlmResult:
    """What a provider returns: the text plus token usage."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(eq=False)
class LlmCall:
    organization_id: uuid.UUID
    provider: LlmProvider
    model: str
    prompt: str
    user_id: uuid.UUID | None = None
    status: LlmCallStatus = LlmCallStatus.PENDING
    reservation_id: uuid.UUID | None = None
    response_text: str | None = None
    response_preview: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    credits_cost: int = 0
    error: str | None = None
    completed_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_pending(self) -> bool:
        return self.status == LlmCallStatus.PENDING

    @classmethod
    def pending(
        cls,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None,
        provider: LlmProvider,
        model: str,
        prompt: str,
        reservation_id: uuid.UUID,
        credits_cost: int,
    ) -> "LlmCall":
        return cls(
            organization_id=organization_id,
            user_id=user_id,
            provider=provider,
            model=model,
            prompt=prompt,
            status=LlmCallStatus.PENDING,
            reservation_id=reservation_id,
            credits_cost=credits_cost,
        )

    def succeed(self, result: LlmResult) -> None:
        self.status = LlmCallStatus.SUCCEEDED
        self.response_text = result.text
        self.response_preview = result.text[:RESPONSE_PREVIEW_CHARS]
        self.tokens_in = result.tokens_in
        self.tokens_out = result.tokens_out
        self.completed_at = _utcnow()

    def fail(self, error: str) -> None:
        self.status = LlmCallStatus.FAILED
        self.error = error[:2000]
        self.completed_at = _utcnow()
