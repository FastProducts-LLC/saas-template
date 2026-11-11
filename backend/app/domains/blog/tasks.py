"""Blog maintenance + AI draft jobs.

`publish_due_posts` is beat-scheduled on the default queue.
`generate_blog_draft` runs on the heavy queue (long LLM call).

Idempotent: GenerateDraftPost exits early unless the job is still pending,
so an acks_late redelivery after a worker death is safe.
"""

from app.core.celery_app import celery_app, run_async
from app.domains.blog.worker import publish_due_posts as _publish_due_posts
from app.domains.blog.worker import run_draft_generation as _run_draft_generation


@celery_app.task(queue="default")
def publish_due_posts() -> int:
    return run_async(_publish_due_posts())


@celery_app.task(queue="heavy")
def generate_blog_draft(job_id: str) -> None:
    run_async(_run_draft_generation(job_id))
