"""Generations API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.error_codes import ERROR_CODES
from app.domains.credits.domain import CreditAction
from app.domains.generations.domain import GENERATION_KINDS, Generation, GenerationStatus


class CreateGenerationRequest(BaseModel):
    kind: CreditAction
    prompt: str = Field(min_length=1, max_length=4000)

    @field_validator("kind")
    @classmethod
    def _must_be_generation_kind(cls, v: CreditAction) -> CreditAction:
        if v not in GENERATION_KINDS:
            raise ValueError(f"'{v.value}' is not a generation action.")
        return v


class GenerationFileUrlOut(BaseModel):
    url: str | None
    expires_in: int | None


class GenerationOut(BaseModel):
    id: uuid.UUID
    kind: CreditAction
    model: str
    prompt: str
    status: GenerationStatus
    credits_cost: int
    mime_type: str | None
    # Catalog copy, never the raw worker exception (that can carry provider
    # endpoints/ids — it stays in the DB + logs, visible to superusers only).
    error: str | None
    error_code: str | None
    has_file: bool
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_entity(cls, g: Generation) -> "GenerationOut":
        return cls(
            id=g.id,
            kind=g.kind,
            model=g.model,
            prompt=g.prompt,
            status=g.status,
            credits_cost=g.credits_cost,
            mime_type=g.mime_type,
            error=ERROR_CODES["ERR_GEN_003"]["user_message"] if g.error else None,
            error_code="ERR_GEN_003" if g.error else None,
            has_file=g.has_file,
            created_at=g.created_at,
            completed_at=g.completed_at,
        )
