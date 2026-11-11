"""Generations domain: AI generation jobs metered by the credit engine.

A `Generation` is one request to an AI provider (Gemini nano-banana image,
OpenAI GPT image, VEO 3.1 video). Each one is tied to a `CreditReservation`:
credits are held when the job is accepted and captured only when the result
is delivered (released on failure) — see `app.domains.credits`.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domains.credits.domain import CreditAction
from app.domains.generations.domain.errors import NotCancelable

# The credit catalog's action values double as the generation kinds.
GENERATION_KINDS = (
    CreditAction.IMAGE_NANO_BANANA,
    CreditAction.IMAGE_GPT,
    CreditAction.VIDEO_VEO,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class GeneratedAsset:
    """Raw provider result — bytes plus their mime type."""

    data: bytes
    mime_type: str


@dataclass(eq=False)
class Generation:
    organization_id: uuid.UUID
    kind: CreditAction
    model: str
    prompt: str
    user_id: uuid.UUID | None = None
    status: GenerationStatus = GenerationStatus.PENDING
    reservation_id: uuid.UUID | None = None
    credits_cost: int = 0
    # Storage key; legacy "<org_id>/<id>.png" values remain valid.
    file_path: str | None = None
    mime_type: str | None = None
    error: str | None = None
    completed_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_pending(self) -> bool:
        return self.status == GenerationStatus.PENDING

    @property
    def is_settled(self) -> bool:
        return self.status in (
            GenerationStatus.SUCCEEDED,
            GenerationStatus.FAILED,
            GenerationStatus.CANCELED,
        )

    @property
    def has_file(self) -> bool:
        return self.file_path is not None

    def cancel(self) -> None:
        if self.status != GenerationStatus.PENDING:
            raise NotCancelable("This generation can no longer be canceled.")
        self.status = GenerationStatus.CANCELED
        self.completed_at = _utcnow()

    def succeed(self, file_path: str, mime_type: str) -> None:
        self.status = GenerationStatus.SUCCEEDED
        self.file_path = file_path
        self.mime_type = mime_type
        self.completed_at = _utcnow()

    def fail(self, error: str) -> None:
        self.status = GenerationStatus.FAILED
        self.error = error[:2000]
        self.completed_at = _utcnow()
