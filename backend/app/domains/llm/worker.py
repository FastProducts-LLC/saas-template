"""LLM worker — the background-job composition root.

`execute_llm_call` runs in a Celery worker with no request context: it
builds its own sessions, runs the provider call with no transaction open,
then finalizes the call (and its credit hold) via the FinalizeLlmCall use
case in a fresh transaction.
"""

import logging
import uuid

from app.core.database import SessionLocal
from app.domains.analytics.interface.deps import build_activity_tracker
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.llm.application.use_cases import FinalizeLlmCall
from app.domains.llm.infrastructure.providers import DispatchingLlmGateway
from app.domains.llm.infrastructure.repositories import SqlAlchemyLlmCallRepository

logger = logging.getLogger(__name__)


def enqueue_llm_call(call_id: uuid.UUID) -> None:
    """Hand the job to the Celery `heavy` queue. Called via FastAPI
    background tasks so it runs *after* the request transaction commits —
    otherwise the worker could race ahead and not find the row."""
    from app.domains.llm.tasks import run_llm_call

    run_llm_call.delay(str(call_id))


async def execute_llm_call(call_id: uuid.UUID) -> None:
    """Worker entry point: run the provider call (no transaction held), then
    finalize the llm call and its credit hold in a fresh transaction."""
    async with SessionLocal() as session:
        call = await SqlAlchemyLlmCallRepository(session).get(call_id)
        if call is None or not call.is_pending:
            return
        provider, prompt = call.provider, call.prompt

    # max_tokens is not persisted on the row; use a generous default that the
    # provider SDK will respect. The request-level cap (8192) is enforced at
    # the schema layer before the job is enqueued.
    gateway = DispatchingLlmGateway()
    try:
        result = await gateway.complete(provider, prompt, max_tokens=8192)
    except Exception as exc:
        logger.exception("LlmCall %s failed", call_id)
        await _finalize(call_id, error=str(exc))
        return
    await _finalize(call_id, result=result)


async def _finalize(
    call_id: uuid.UUID,
    *,
    result=None,
    error: str | None = None,
) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            use_case = FinalizeLlmCall(
                SqlAlchemyLlmCallRepository(session),
                build_credit_engine(session),
                build_activity_tracker(session),
            )
            await use_case.execute(call_id, result=result, error=error)
