"""Generation worker — the background-job composition root.

`execute_generation` runs in a Celery worker with no request context: it
builds its own sessions, runs the provider call with no transaction open,
then finalizes the job (and its credit hold) via the FinalizeGeneration use
case in a fresh transaction.
"""

import logging
import uuid

from app.core.database import SessionLocal
from app.core.storage.base import StorageError
from app.domains.analytics.interface.deps import build_activity_tracker
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.generations.application.use_cases import FinalizeGeneration
from app.domains.generations.infrastructure.media_store import StorageMediaStore
from app.domains.generations.infrastructure.providers import DispatchingProviderGateway
from app.domains.generations.infrastructure.repositories import SqlAlchemyGenerationRepository

logger = logging.getLogger(__name__)


def enqueue_generation(generation_id: uuid.UUID) -> None:
    """Hand the job to the Celery `heavy` queue. Called via FastAPI
    background tasks so it runs *after* the request transaction commits —
    otherwise the worker could race ahead and not find the row."""
    from app.domains.generations.tasks import run_generation

    run_generation.delay(str(generation_id))


async def execute_generation(generation_id: uuid.UUID) -> None:
    """Worker entry point: run the provider call (no transaction held), then
    finalize the generation and its credit hold in a fresh transaction."""
    async with SessionLocal() as session:
        generation = await SqlAlchemyGenerationRepository(session).get(generation_id)
        if generation is None or not generation.is_pending:
            return
        org_id, kind, prompt = generation.organization_id, generation.kind, generation.prompt

    store = StorageMediaStore()
    try:
        asset = await DispatchingProviderGateway().run(kind, prompt)
        name = f"{generation_id}.{store.extension_for(asset.mime_type)}"
        file_path = await store.save(org_id, name, asset)
    except StorageError:
        # SDK exception chains can contain endpoint credentials or signed URLs.
        logger.warning("Storage failed for generation %s", generation_id)
        await _finalize(generation_id, error="Result storage is temporarily unavailable.")
        return
    except Exception as exc:
        logger.exception("Generation %s failed", generation_id)
        await _finalize(generation_id, error=str(exc))
        return
    await _finalize(generation_id, file_path=file_path, mime_type=asset.mime_type)


async def _finalize(
    generation_id: uuid.UUID,
    *,
    file_path: str | None = None,
    mime_type: str | None = None,
    error: str | None = None,
) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            use_case = FinalizeGeneration(
                SqlAlchemyGenerationRepository(session),
                build_credit_engine(session),
                build_activity_tracker(session),
            )
            await use_case.execute(
                generation_id, file_path=file_path, mime_type=mime_type, error=error
            )
