"""Audit maintenance jobs — daily retention purge (beat-scheduled).

Idempotent: the purge deletes only rows past the cutoff, so an acks_late
redelivery after a worker death is safe.
"""

from app.core.celery_app import celery_app, run_async
from app.domains.audit.worker import purge_expired_audit_events


@celery_app.task(queue="default")
def purge_audit_events() -> int:
    return run_async(purge_expired_audit_events())
