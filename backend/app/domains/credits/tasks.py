"""Credits maintenance jobs — periodic stale-hold sweep (beat-scheduled).

Idempotent: settling an org twice is a no-op (already-settled holds are
skipped under the wallet lock), so an acks_late redelivery after a worker
death is safe.
"""

from app.core.celery_app import celery_app, run_async
from app.domains.credits.worker import sweep_stale_reservations


@celery_app.task(queue="default")
def expire_stale_reservations() -> int:
    return run_async(sweep_stale_reservations())
