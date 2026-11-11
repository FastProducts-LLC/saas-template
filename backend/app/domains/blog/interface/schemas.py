"""Blog HTTP schemas — Pydantic at the edge only."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.core.policy import (
    BLOG_COVER_IMAGE_URL_MAX_LENGTH,
    BLOG_EXCERPT_MAX_LENGTH,
    BLOG_MAX_TAGS,
    BLOG_META_DESCRIPTION_MAX_LENGTH,
    BLOG_META_TITLE_MAX_LENGTH,
    BLOG_SLUG_MAX_LENGTH,
    BLOG_TAG_MAX_LENGTH,
    BLOG_TITLE_MAX_LENGTH,
)
from app.domains.blog.domain.entities import BlogGenerationJob, BlogPost

PostStatusLiteral = Literal["draft", "published", "archived", "scheduled"]
TagStr = Annotated[str, Field(max_length=BLOG_TAG_MAX_LENGTH)]


class BlogPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=BLOG_TITLE_MAX_LENGTH)
    # Omitted/blank → derived from the title.
    slug: str | None = Field(default=None, max_length=BLOG_SLUG_MAX_LENGTH)
    excerpt: str = Field(min_length=1, max_length=BLOG_EXCERPT_MAX_LENGTH)
    content: str = Field(min_length=1)
    cover_image: str | None = Field(default=None, max_length=BLOG_COVER_IMAGE_URL_MAX_LENGTH)
    meta_title: str | None = Field(default=None, max_length=BLOG_META_TITLE_MAX_LENGTH)
    meta_description: str | None = Field(default=None, max_length=BLOG_META_DESCRIPTION_MAX_LENGTH)
    status: PostStatusLiteral = "draft"
    tags: list[TagStr] = Field(default_factory=list, max_length=BLOG_MAX_TAGS)


class BlogPostUpdate(BaseModel):
    """Partial update — only fields the client sends are applied."""

    title: str | None = Field(default=None, min_length=1, max_length=BLOG_TITLE_MAX_LENGTH)
    slug: str | None = Field(default=None, max_length=BLOG_SLUG_MAX_LENGTH)
    excerpt: str | None = Field(default=None, min_length=1, max_length=BLOG_EXCERPT_MAX_LENGTH)
    content: str | None = Field(default=None, min_length=1)
    cover_image: str | None = Field(default=None, max_length=BLOG_COVER_IMAGE_URL_MAX_LENGTH)
    meta_title: str | None = Field(default=None, max_length=BLOG_META_TITLE_MAX_LENGTH)
    meta_description: str | None = Field(default=None, max_length=BLOG_META_DESCRIPTION_MAX_LENGTH)
    status: PostStatusLiteral | None = None
    # Go-live time when status="scheduled"; feeds entity.schedule(), not a column.
    scheduled_for: datetime | None = None
    tags: list[TagStr] | None = Field(default=None, max_length=BLOG_MAX_TAGS)

    @model_validator(mode="after")
    def _validate_schedule(self) -> Self:
        if self.status == "scheduled" and self.scheduled_for is None:
            raise ValueError("scheduled_for is required when scheduling")
        if self.scheduled_for is not None:
            if self.scheduled_for.tzinfo is None:
                raise ValueError("scheduled_for must be timezone-aware")
            if self.scheduled_for <= datetime.now(UTC):
                raise ValueError("scheduled_for must be in the future")
        return self


class BlogPostSummaryOut(BaseModel):
    """Public list card — no body, no draft-only fields."""

    id: uuid.UUID
    title: str
    slug: str
    excerpt: str
    cover_image: str | None
    published_at: datetime | None
    tags: list[str]

    @classmethod
    def from_entity(cls, post: BlogPost) -> "BlogPostSummaryOut":
        return cls(
            id=post.id,
            title=post.title,
            slug=post.slug,
            excerpt=post.excerpt,
            cover_image=post.cover_image,
            published_at=post.published_at,
            tags=list(post.tags or []),
        )


class BlogPostOut(BlogPostSummaryOut):
    """Public article detail."""

    content: str
    meta_title: str | None
    meta_description: str | None
    updated_at: datetime
    author_name: str | None = None
    related: list[BlogPostSummaryOut] = Field(default_factory=list)

    @classmethod
    def from_entity(
        cls,
        post: BlogPost,
        *,
        author_name: str | None = None,
        related: list[BlogPost] | None = None,
    ) -> "BlogPostOut":
        return cls(
            id=post.id,
            title=post.title,
            slug=post.slug,
            excerpt=post.excerpt,
            cover_image=post.cover_image,
            published_at=post.published_at,
            tags=list(post.tags or []),
            content=post.content,
            meta_title=post.meta_title,
            meta_description=post.meta_description,
            updated_at=post.updated_at,
            author_name=author_name,
            related=[BlogPostSummaryOut.from_entity(p) for p in (related or [])],
        )


class AdminBlogPostOut(BaseModel):
    """Full post for the admin console — any status."""

    id: uuid.UUID
    title: str
    slug: str
    excerpt: str
    content: str
    cover_image: str | None
    meta_title: str | None
    meta_description: str | None
    status: PostStatusLiteral
    published_at: datetime | None
    author_id: uuid.UUID | None
    view_count: int
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, post: BlogPost) -> "AdminBlogPostOut":
        return cls(
            id=post.id,
            title=post.title,
            slug=post.slug,
            excerpt=post.excerpt,
            content=post.content,
            cover_image=post.cover_image,
            meta_title=post.meta_title,
            meta_description=post.meta_description,
            status=post.status.value,  # type: ignore[arg-type]
            published_at=post.published_at,
            author_id=post.author_id,
            view_count=post.view_count,
            tags=list(post.tags or []),
            created_at=post.created_at,
            updated_at=post.updated_at,
        )


class BlogPostPage(BaseModel):
    items: list[BlogPostSummaryOut]
    total: int
    page: int
    page_size: int


class AdminBlogPostPage(BaseModel):
    items: list[AdminBlogPostOut]
    total: int
    page: int
    page_size: int


class BlogTagCountOut(BaseModel):
    tag: str
    count: int


class PreviewLinkOut(BaseModel):
    """Shareable draft-preview URL minted for a post."""

    token: str
    url: str
    expires_in_days: int


ProviderLiteral = Literal["anthropic", "openai", "gemini"]
GenerationStatusLiteral = Literal["pending", "succeeded", "failed"]


class DraftGenerateRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(default=None, max_length=500)
    provider: ProviderLiteral = "anthropic"


class GenerationJobOut(BaseModel):
    id: uuid.UUID
    topic: str
    keywords: list[str]
    notes: str | None
    provider: str
    status: GenerationStatusLiteral
    error: str | None
    post_id: uuid.UUID | None
    requested_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, job: BlogGenerationJob) -> "GenerationJobOut":
        return cls(
            id=job.id,
            topic=job.topic,
            keywords=list(job.keywords or []),
            notes=job.notes,
            provider=job.provider,
            status=job.status.value,  # type: ignore[arg-type]
            error=job.error,
            post_id=job.post_id,
            requested_by_id=job.requested_by_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
