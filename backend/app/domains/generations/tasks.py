"""Generation jobs — long-running provider calls on the `heavy` queue.

Idempotent by design: `execute_generation` exits early unless the job is
still pending, so an acks_late redelivery after a worker death can't run a
generation (or settle its credit hold) twice. A crash mid-run self-corrects
too: the credit hold expires and is refunded on the next wallet touch or by
the periodic sweep in `app.domains.credits.tasks`.
"""

import uuid

from app.core.celery_app import celery_app, run_async
from app.domains.generations.worker import execute_generation

# VEO video jobs poll a long-running operation; give them more headroom than
# the global 540s/600s defaults. SoftTimeLimitExceeded surfaces inside
# execute_generation's try block, which fails the job and refunds the hold.
GENERATION_SOFT_TIME_LIMIT = 1740
GENERATION_TIME_LIMIT = 1800


@celery_app.task(
    queue="heavy",
    soft_time_limit=GENERATION_SOFT_TIME_LIMIT,
    time_limit=GENERATION_TIME_LIMIT,
)
def run_generation(generation_id: str) -> None:
    run_async(execute_generation(uuid.UUID(generation_id)))
