"""Blog composition root — the ONLY place use cases meet concrete adapters."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.blog.application import use_cases as uc
from app.domains.blog.application.generation import RequestDraftGeneration
from app.domains.blog.infrastructure.repositories import (
    SqlAlchemyBlogGenerationJobRepository,
    SqlAlchemyBlogPostRepository,
)

DB = Annotated[AsyncSession, Depends(get_db)]


def get_blog_post_repo(db: DB) -> SqlAlchemyBlogPostRepository:
    return SqlAlchemyBlogPostRepository(db)


def get_blog_generation_job_repo(db: DB) -> SqlAlchemyBlogGenerationJobRepository:
    return SqlAlchemyBlogGenerationJobRepository(db)


def get_create_blog_post(db: DB) -> uc.CreateBlogPost:
    return uc.CreateBlogPost(SqlAlchemyBlogPostRepository(db))


def get_update_blog_post(db: DB) -> uc.UpdateBlogPost:
    return uc.UpdateBlogPost(SqlAlchemyBlogPostRepository(db))


def get_delete_blog_post(db: DB) -> uc.DeleteBlogPost:
    return uc.DeleteBlogPost(SqlAlchemyBlogPostRepository(db))


def get_get_published_post(db: DB) -> uc.GetPublishedPost:
    return uc.GetPublishedPost(SqlAlchemyBlogPostRepository(db))


def get_get_preview_post(db: DB) -> uc.GetPreviewPost:
    return uc.GetPreviewPost(SqlAlchemyBlogPostRepository(db))


def get_request_draft_generation(db: DB) -> RequestDraftGeneration:
    return RequestDraftGeneration(SqlAlchemyBlogGenerationJobRepository(db))
