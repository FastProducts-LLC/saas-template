"""Blog background jobs — the composition root (no request context).

Publishes scheduled posts whose published_at has elapsed. Idempotent: a
published post is no longer due, so an acks_late redelivery is a no-op.

Also runs AI draft generation on the heavy queue — LLM call + draft create
inside one worker transaction; unexpected failures mark the job failed in a
fresh session so it never hangs in pending.
"""

import logging
import uuid
from datetime import UTC, datetime

from app.core.database import SessionLocal
from app.domains.blog.application.generation import GenerateDraftPost
from app.domains.blog.domain.entities import GenerationJobStatus, PostStatus
from app.domains.blog.infrastructure.repositories import (
    SqlAlchemyBlogGenerationJobRepository,
    SqlAlchemyBlogPostRepository,
)
from app.domains.llm.interface.deps import get_llm_gateway

logger = logging.getLogger(__name__)


def enqueue_draft_generation(job_id: uuid.UUID) -> None:
    """Hand the job to the Celery `heavy` queue.

    Called via FastAPI BackgroundTasks so it runs *after* the request
    transaction commits — otherwise the worker could race ahead and not find
    the row. Enqueue-after-commit is best-effort (get_db commits on response).
    """
    from app.domains.blog.tasks import generate_blog_draft

    generate_blog_draft.delay(str(job_id))


async def publish_due_posts() -> int:
    """Flip due scheduled posts to published; returns count published."""
    async with SessionLocal() as session:
        async with session.begin():
            repo = SqlAlchemyBlogPostRepository(session)
            posts = await repo.list_due_scheduled(now=datetime.now(UTC))
            for post in posts:
                post.apply_status(PostStatus.PUBLISHED)
                post.touch()
            count = len(posts)
    if count:
        logger.info("Published %d due scheduled blog post(s)", count)
    return count


async def run_draft_generation(job_id: str) -> None:
    """Worker entry: generate a draft post for a pending BlogGenerationJob."""
    jid = uuid.UUID(job_id)
    try:
        async with SessionLocal() as session:
            async with session.begin():
                jobs = SqlAlchemyBlogGenerationJobRepository(session)
                posts = SqlAlchemyBlogPostRepository(session)
                use_case = GenerateDraftPost(jobs, posts, get_llm_gateway())
                await use_case.execute(jid)
    except Exception as exc:
        logger.exception("Blog draft generation %s failed", job_id)
        async with SessionLocal() as session:
            async with session.begin():
                jobs = SqlAlchemyBlogGenerationJobRepository(session)
                job = await jobs.get(jid)
                if job is not None and job.status is GenerationJobStatus.PENDING:
                    job.fail(str(exc)[:500])
