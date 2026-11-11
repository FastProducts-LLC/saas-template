"""Blog use cases."""

import uuid
from dataclasses import dataclass
from typing import Any

from app.domains.blog.application.ports import BlogPostRepository
from app.domains.blog.domain.entities import BlogPost, PostStatus
from app.domains.blog.domain.errors import BlogPostNotFound, BlogSlugConflict
from app.domains.blog.domain.services import normalize_tags, slugify


class CreateBlogPost:
    def __init__(self, repo: BlogPostRepository) -> None:
        self.repo = repo

    async def execute(
        self,
        *,
        title: str,
        slug: str | None,
        excerpt: str,
        content: str,
        cover_image: str | None,
        meta_title: str | None,
        meta_description: str | None,
        status: PostStatus,
        author_id: uuid.UUID | None,
        tags: list[str] | None = None,
    ) -> BlogPost:
        final_slug = (slug or "").strip() or slugify(title)
        if await self.repo.get_by_slug(final_slug):
            raise BlogSlugConflict("A post with this slug already exists.")
        post = BlogPost(
            title=title.strip(),
            slug=final_slug,
            excerpt=excerpt.strip(),
            content=content,
            cover_image=cover_image,
            meta_title=meta_title,
            meta_description=meta_description,
            author_id=author_id,
            tags=normalize_tags(tags or []),
        )
        post.apply_status(status)
        await self.repo.add(post)
        return post


class UpdateBlogPost:
    """Partial update. `updates` holds only the fields the caller sent."""

    def __init__(self, repo: BlogPostRepository) -> None:
        self.repo = repo

    async def execute(self, post_id: uuid.UUID, *, updates: dict[str, Any]) -> BlogPost:
        post = await self.repo.get(post_id)
        if post is None:
            raise BlogPostNotFound("Blog post not found.")

        if "title" in updates:
            post.title = str(updates["title"]).strip()
        if "slug" in updates:
            new_slug = str(updates["slug"] or "").strip() or slugify(post.title)
            if new_slug != post.slug:
                existing = await self.repo.get_by_slug(new_slug)
                if existing is not None and existing.id != post.id:
                    raise BlogSlugConflict("A post with this slug already exists.")
                post.slug = new_slug
        for attr in ("excerpt", "content", "cover_image", "meta_title", "meta_description"):
            if attr in updates:
                setattr(post, attr, updates[attr])
        if "tags" in updates:
            post.tags = normalize_tags(list(updates["tags"] or []))
        if "status" in updates:
            if updates["status"] == PostStatus.SCHEDULED.value:
                # scheduled_for feeds schedule(); never written as an entity attr.
                post.schedule(updates["scheduled_for"])
            else:
                post.apply_status(PostStatus(updates["status"]))

        post.touch()
        return post


class DeleteBlogPost:
    def __init__(self, repo: BlogPostRepository) -> None:
        self.repo = repo

    async def execute(self, post_id: uuid.UUID) -> None:
        post = await self.repo.get(post_id)
        if post is None:
            raise BlogPostNotFound("Blog post not found.")
        await self.repo.delete(post)


@dataclass(frozen=True)
class PublishedPostResult:
    post: BlogPost
    author_name: str | None
    related: list[BlogPost]


class GetPublishedPost:
    """Public read by slug — drafts and archived posts 404."""

    def __init__(self, repo: BlogPostRepository) -> None:
        self.repo = repo

    async def execute(self, slug: str) -> PublishedPostResult:
        post = await self.repo.get_by_slug(slug)
        if post is None or not post.is_published:
            raise BlogPostNotFound("Blog post not found.")
        await self.repo.increment_view_count(post.id)
        author_name = None
        if post.author_id is not None:
            author_name = await self.repo.get_author_name(post.author_id)
        related = await self.repo.list_related(post=post)
        return PublishedPostResult(post=post, author_name=author_name, related=related)


@dataclass(frozen=True)
class PreviewPostResult:
    post: BlogPost
    author_name: str | None


class GetPreviewPost:
    """Token-gated read by id — any status, no view_count bump, no related."""

    def __init__(self, repo: BlogPostRepository) -> None:
        self.repo = repo

    async def execute(self, post_id: uuid.UUID) -> PreviewPostResult:
        post = await self.repo.get(post_id)
        if post is None:
            raise BlogPostNotFound("Blog post not found.")
        author_name = None
        if post.author_id is not None:
            author_name = await self.repo.get_author_name(post.author_id)
        return PreviewPostResult(post=post, author_name=author_name)
