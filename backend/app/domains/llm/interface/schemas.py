"""LLM API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.error_codes import ERROR_CODES
from app.domains.llm.domain.entities import LlmCall, LlmCallStatus, LlmProvider


class CompleteRequest(BaseModel):
    provider: LlmProvider
    prompt: str = Field(min_length=1, max_length=8000)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class LlmCallOut(BaseModel):
    id: uuid.UUID
    provider: LlmProvider
    model: str
    prompt: str
    status: LlmCallStatus
    response_text: str | None
    tokens_in: int
    tokens_out: int
    credits_cost: int
    # Catalog copy, never the raw worker exception (that can carry provider
    # endpoints/ids — it stays in the DB + logs, visible to superusers only).
    error: str | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_call(cls, call: LlmCall) -> "LlmCallOut":
        return cls(
            id=call.id,
            provider=call.provider,
            model=call.model,
            prompt=call.prompt,
            status=call.status,
            response_text=call.response_text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            credits_cost=call.credits_cost,
            error=ERROR_CODES["ERR_LLM_002"]["user_message"] if call.error else None,
            error_code="ERR_LLM_002" if call.error else None,
            created_at=call.created_at,
            completed_at=call.completed_at,
        )
