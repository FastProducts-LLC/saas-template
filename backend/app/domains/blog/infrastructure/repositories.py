"""Blog SQLAlchemy repository."""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, literal_column, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.blog.infrastructure.orm  # noqa: F401
from app.domains.auth.domain import User
from app.domains.blog.domain.entities import BlogGenerationJob, BlogPost, PostStatus
from app.domains.blog.domain.errors import BlogSlugConflict
from app.domains.blog.infrastructure.orm import blog_posts_table


class SqlAlchemyBlogPostRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, post: BlogPost) -> None:
        self.db.add(post)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            # Unique-slug race backstop: the use case pre-checks, the index decides.
            if "slug" in str(exc.orig):
                raise BlogSlugConflict("A post with this slug already exists.") from exc
            raise

    async def get(self, post_id: uuid.UUID) -> BlogPost | None:
        return await self.db.get(BlogPost, post_id)

    async def get_by_slug(self, slug: str) -> BlogPost | None:
        return (
            await self.db.execute(select(BlogPost).where(BlogPost.slug == slug))
        ).scalar_one_or_none()

    async def list_published(
        self, *, q: str | None = None, tag: str | None = None, limit: int, offset: int
    ) -> tuple[list[BlogPost], int]:
        filters = [BlogPost.status == PostStatus.PUBLISHED]
        if tag:
            filters.append(BlogPost.tags.contains([tag]))
        if q:
            # Inline 'english' and separator spaces as SQL literals so the
            # predicate matches the functional index ix_blog_posts_search
            # (bound parameters would force a seq scan).
            _SPACE = literal_column("' '")
            document = BlogPost.title + _SPACE + BlogPost.excerpt + _SPACE + BlogPost.content
            filters.append(
                func.to_tsvector(literal_column("'english'"), document).op("@@")(
                    func.plainto_tsquery("english", q)
                )
            )

        where = and_(*filters)
        total = (
            await self.db.execute(select(func.count()).select_from(BlogPost).where(where))
        ).scalar_one()
        stmt = (
            select(BlogPost)
            .where(where)
            .order_by(BlogPost.published_at.desc(), BlogPost.id)
            .limit(limit)
            .offset(offset)
        )
        items = list((await self.db.execute(stmt)).scalars())
        return items, total

    async def list_all(
        self, *, status: PostStatus | None, limit: int, offset: int
    ) -> tuple[list[BlogPost], int]:
        filters = []
        if status is not None:
            filters.append(BlogPost.status == status)

        count_stmt = select(func.count()).select_from(BlogPost)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = select(BlogPost)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(BlogPost.created_at.desc(), BlogPost.id).limit(limit).offset(offset)
        items = list((await self.db.execute(stmt)).scalars())
        return items, total

    async def list_due_scheduled(self, *, now: datetime) -> list[BlogPost]:
        stmt = select(BlogPost).where(
            BlogPost.status == PostStatus.SCHEDULED,
            BlogPost.published_at <= now,
        )
        return list((await self.db.execute(stmt)).scalars())

    async def list_related(self, *, post: BlogPost, limit: int = 3) -> list[BlogPost]:
        picked: list[BlogPost] = []
        exclude_ids = {post.id}

        if post.tags:
            stmt = (
                select(BlogPost)
                .where(
                    BlogPost.status == PostStatus.PUBLISHED,
                    BlogPost.id != post.id,
                    BlogPost.tags.overlap(post.tags),
                )
                .order_by(BlogPost.published_at.desc(), BlogPost.id)
                .limit(limit)
            )
            picked = list((await self.db.execute(stmt)).scalars())
            exclude_ids.update(p.id for p in picked)

        if len(picked) < limit:
            stmt = (
                select(BlogPost)
                .where(
                    BlogPost.status == PostStatus.PUBLISHED,
                    BlogPost.id.notin_(exclude_ids),
                )
                .order_by(BlogPost.published_at.desc(), BlogPost.id)
                .limit(limit - len(picked))
            )
            picked.extend((await self.db.execute(stmt)).scalars())

        return picked

    async def get_author_name(self, author_id: uuid.UUID) -> str | None:
        row = (
            await self.db.execute(
                select(User.first_name, User.last_name).where(User.id == author_id)
            )
        ).one_or_none()
        if row is None:
            return None
        name = f"{row.first_name} {row.last_name}".strip()
        return name or None

    async def list_tag_counts(self) -> list[tuple[str, int]]:
        result = await self.db.execute(
            text(
                """
                SELECT tag, COUNT(*) AS count
                FROM blog_posts, unnest(tags) AS tag
                WHERE status = 'published'
                GROUP BY tag
                ORDER BY count DESC, tag ASC
                """
            )
        )
        return [(row.tag, int(row.count)) for row in result]

    async def delete(self, post: BlogPost) -> None:
        await self.db.delete(post)
        await self.db.flush()

    async def increment_view_count(self, post_id: uuid.UUID) -> None:
        await self.db.execute(
            update(blog_posts_table)
            .where(blog_posts_table.c.id == post_id)
            .values(view_count=blog_posts_table.c.view_count + 1)
        )


class SqlAlchemyBlogGenerationJobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, job: BlogGenerationJob) -> None:
        self.db.add(job)
        await self.db.flush()

    async def get(self, job_id: uuid.UUID) -> BlogGenerationJob | None:
        return await self.db.get(BlogGenerationJob, job_id)

    async def list_recent(self, *, limit: int = 20) -> list[BlogGenerationJob]:
        stmt = (
            select(BlogGenerationJob)
            .order_by(BlogGenerationJob.created_at.desc(), BlogGenerationJob.id)
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars())
