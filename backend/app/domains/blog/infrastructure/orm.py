"""Blog persistence mapping — table + imperative mapping."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.database import Base
from app.domains.blog.domain.entities import (
    BlogGenerationJob,
    BlogPost,
    GenerationJobStatus,
    PostStatus,
)


def _str_enum(enum_cls, *, length: int):
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


blog_posts_table = sa.Table(
    "blog_posts",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("slug", sa.String(80), nullable=False, unique=True, index=True),
    sa.Column("excerpt", sa.String(500), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("cover_image", sa.String(500), nullable=True),
    sa.Column("meta_title", sa.String(70), nullable=True),
    sa.Column("meta_description", sa.String(160), nullable=True),
    sa.Column("status", _str_enum(PostStatus, length=16), nullable=False, index=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True, index=True),
    sa.Column(
        "author_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
    sa.Column(
        "tags",
        postgresql.ARRAY(sa.String(40)),
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        index=True,
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_blog_posts_tags", "tags", postgresql_using="gin"),
)

blog_generation_jobs_table = sa.Table(
    "blog_generation_jobs",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("topic", sa.String(200), nullable=False),
    sa.Column(
        "keywords",
        postgresql.ARRAY(sa.String(40)),
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column("notes", sa.String(500), nullable=True),
    sa.Column("provider", sa.String(16), nullable=False),
    sa.Column("status", _str_enum(GenerationJobStatus, length=16), nullable=False, index=True),
    sa.Column("error", sa.Text(), nullable=True),
    sa.Column(
        "post_id",
        sa.Uuid(),
        sa.ForeignKey("blog_posts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "requested_by_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_blog_generation_jobs_status_created_at", "status", "created_at"),
)

Base.registry.map_imperatively(BlogPost, blog_posts_table)
Base.registry.map_imperatively(BlogGenerationJob, blog_generation_jobs_table)
