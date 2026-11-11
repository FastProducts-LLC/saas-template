"""Privacy retention — nightly payload minimization (beat-scheduled).

Idempotent: purge skips already-cleared rows, so acks_late redelivery is safe.
"""

from app.core.celery_app import celery_app, run_async
from app.domains.privacy_requests.worker import purge_stale_privacy_payloads


@celery_app.task(queue="default")
def purge_privacy_request_payloads() -> dict:
    return run_async(purge_stale_privacy_payloads())
