"""Celery application: Valkey broker/results, named queues, per-slice task discovery.

Queues
------
- ``default``  short, latency-sensitive work (emails, webhook fan-out)
- ``heavy``    long-running / CPU-bound work (generations, imports, exports)

Route a task at definition time (``@celery_app.task(queue="heavy")``) or
centrally in ``task_routes`` below. Dev and prod each run dedicated workers
per queue (``worker`` -> ``-Q default``, ``worker-heavy`` -> ``-Q heavy``) so
long heavy jobs can never starve latency-sensitive default work.

Tasks live in ``tasks.py`` inside each domain slice
(``app/domains/<name>/tasks.py``) and are autodiscovered — no registration
step. Example:

    from app.core.celery_app import celery_app, run_async

    @celery_app.task(queue="heavy")
    def generate_report(org_id: str) -> None:
        run_async(_generate_report(org_id))
"""

import asyncio
import pkgutil
import ssl
from collections.abc import Coroutine
from typing import Any

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app import domains
from app.core.config import settings
from app.core.observability import setup_sentry

# Worker errors report to Sentry too (no-op unless SENTRY_DSN is set); the
# sentry-sdk Celery integration hooks task failures automatically.
setup_sentry()

_broker_url = settings.celery_broker_url
_result_backend = settings.celery_result_backend


def _feature_packages() -> list[str]:
    """Every package under app/domains — autodiscovery scans each for tasks.py."""
    return [f"app.domains.{m.name}" for m in pkgutil.iter_modules(domains.__path__) if m.ispkg]


celery_app = Celery("app", broker=_broker_url, backend=_result_backend)

celery_app.conf.update(
    # --- Queues & routing ---
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("heavy", routing_key="heavy"),
    ),
    task_routes={
        # Central routing by task-name pattern (overrides nothing set per-task), e.g.:
        # "app.domains.generations.tasks.*": {"queue": "heavy"},
    },
    # --- Reliability ---
    # acks_late + reject_on_worker_lost: a task whose worker dies mid-run is
    # re-delivered instead of silently lost — tasks must therefore be idempotent.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # don't hoard tasks; fair dispatch across workers
    broker_connection_retry_on_startup=True,
    # --- Limits ---
    task_soft_time_limit=540,  # SoftTimeLimitExceeded raised in-task: clean up
    task_time_limit=600,  # hard kill 60s later
    result_expires=3600,  # results are transient; don't let Valkey fill up
    # --- Serialization / time ---
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# DigitalOcean managed Valkey uses rediss:// — Celery needs cert verification
# configured explicitly for TLS broker/backend connections.
if _broker_url.startswith("rediss://"):
    celery_app.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
if _result_backend.startswith("rediss://"):
    celery_app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

celery_app.autodiscover_tasks(_feature_packages() + ["app.core.email"])

# Scheduled (beat) tasks. Schedules are cron-style; tasks must be idempotent
# (beat is single-instance, but acks_late can redeliver a run).
celery_app.conf.beat_schedule = {
    "cleanup-pending-file-uploads": {
        "task": "app.domains.files.tasks.cleanup_pending_uploads",
        "schedule": crontab(minute=0),
    },
    # Refund expired credit holds for dormant orgs. Lazy settlement covers
    # any org that touches its wallet; this bounds refund latency for orgs
    # that don't (e.g. a worker crashed on their last action).
    "expire-stale-credit-reservations": {
        "task": "app.domains.credits.tasks.expire_stale_reservations",
        "schedule": crontab(minute="*/10"),
    },
    # Delete refresh tokens long past expiry/revocation — bounds table growth.
    "purge-expired-refresh-tokens": {
        "task": "app.domains.auth.tasks.purge_refresh_tokens",
        "schedule": crontab(hour=3, minute=30),
    },
    # Drop raw privacy-request intake PII past retention;
    # keep audit metadata (status, hashes, provider refs) longer.
    "purge-privacy-request-payloads": {
        "task": "app.domains.privacy_requests.tasks.purge_privacy_request_payloads",
        "schedule": crontab(hour=4, minute=15),
    },
    # Security-event trail retention (AUDIT_RETENTION_DAYS, default 365) —
    # bounds both table growth and how long login-failure PII is kept.
    "purge-audit-events": {
        "task": "app.domains.audit.tasks.purge_audit_events",
        "schedule": crontab(hour=4, minute=45),
    },
    # First-party product-analytics retention (shared/policy.toml
    # [analytics].activity_event_retention_days — the number the privacy
    # policy quotes). Batched deletes; daily keeps each run small.
    "purge-activity-events": {
        "task": "app.domains.analytics.tasks.purge_activity_events",
        "schedule": crontab(hour=5, minute=15),
    },
    # Flip due scheduled blog posts to published (go-live time = published_at).
    # Every minute bounds publish latency; idempotent, so overlap is harmless.
    "publish-due-blog-posts": {
        "task": "app.domains.blog.tasks.publish_due_posts",
        "schedule": crontab(minute="*"),
    },
}


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Bridge Celery's sync tasks to the async app code (services, repositories).

    Each task run gets a fresh event loop, so loop-bound resources must not
    leak between runs: the SQLAlchemy engine pools connections on the loop
    that created them, hence the dispose() before the loop closes.
    """

    async def _wrapped() -> Any:
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(name="app.ping")
def ping() -> str:
    """Smoke-test task: `celery -A app.core.celery_app call app.ping`."""
    return "pong"
