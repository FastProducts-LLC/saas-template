"""Hourly idempotent cleanup of abandoned upload slots."""

from app.core.celery_app import celery_app, run_async
from app.domains.files.worker import sweep_stale_uploads


@celery_app.task(queue="default")
def cleanup_pending_uploads() -> int:
    return run_async(sweep_stale_uploads())
