"""Blog domain entities — pure Python, zero framework/ORM imports."""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    SCHEDULED = "scheduled"


class GenerationJobStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(eq=False)
class BlogPost:
    """A blog article. Global (not tenant-scoped); authored by superusers."""

    title: str
    slug: str
    excerpt: str
    content: str
    cover_image: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    status: PostStatus = PostStatus.DRAFT
    # Set on FIRST publish only; survives unpublish/republish so the public
    # ordering is stable. For SCHEDULED posts this holds the future go-live time.
    published_at: datetime | None = None
    author_id: uuid.UUID | None = None
    view_count: int = 0
    tags: list[str] = field(default_factory=list)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def is_published(self) -> bool:
        return self.status is PostStatus.PUBLISHED

    def apply_status(self, new_status: PostStatus) -> None:
        self.status = new_status
        if new_status is PostStatus.PUBLISHED and self.published_at is None:
            self.published_at = _utcnow()

    def schedule(self, at: datetime) -> None:
        """Queue this post to go live at `at` (stored in published_at)."""
        self.status = PostStatus.SCHEDULED
        self.published_at = at

    def touch(self) -> None:
        self.updated_at = _utcnow()


@dataclass(eq=False)
class BlogGenerationJob:
    """Superuser AI draft request. Platform-cost; no credit metering."""

    topic: str
    keywords: list[str] = field(default_factory=list)
    notes: str | None = None
    provider: str = "anthropic"
    status: GenerationJobStatus = GenerationJobStatus.PENDING
    error: str | None = None
    post_id: uuid.UUID | None = None
    requested_by_id: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def succeed(self, post_id: uuid.UUID) -> None:
        self.status = GenerationJobStatus.SUCCEEDED
        self.post_id = post_id
        self.error = None
        self.updated_at = _utcnow()

    def fail(self, error: str) -> None:
        self.status = GenerationJobStatus.FAILED
        self.error = error[:500]
        self.updated_at = _utcnow()
