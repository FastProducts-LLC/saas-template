"""LLM completion jobs — provider calls on the `heavy` queue.

Idempotent by design: `execute_llm_call` exits early unless the call is
still pending, so an acks_late redelivery after a worker death can't run a
completion (or settle its credit hold) twice. A crash mid-run self-corrects
too: the credit hold expires and is refunded on the next wallet touch or by
the periodic sweep in `app.domains.credits.tasks`.
"""

import uuid

from app.core.celery_app import celery_app, run_async
from app.domains.llm.worker import execute_llm_call


@celery_app.task(queue="heavy")
def run_llm_call(call_id: str) -> None:
    run_async(execute_llm_call(uuid.UUID(call_id)))
