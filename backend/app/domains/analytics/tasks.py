"""Analytics maintenance jobs — daily retention purge (beat-scheduled).

Idempotent: the purge deletes only rows past the cutoff, so an acks_late
redelivery after a worker death is safe.
"""

from app.core.celery_app import celery_app, run_async
from app.domains.analytics.worker import purge_expired_activity_events


@celery_app.task(queue="default")
def purge_activity_events() -> int:
    return run_async(purge_expired_activity_events())
