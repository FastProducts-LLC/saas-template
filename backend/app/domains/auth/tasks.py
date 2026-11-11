"""Auth maintenance jobs — nightly refresh-token purge (beat-scheduled).

Idempotent: a purge deletes only rows already unusable, so an acks_late
redelivery after a worker death is safe.
"""

from app.core.celery_app import celery_app, run_async
from app.domains.auth.worker import purge_expired_refresh_tokens


@celery_app.task(queue="default")
def purge_refresh_tokens() -> int:
    return run_async(purge_expired_refresh_tokens())
