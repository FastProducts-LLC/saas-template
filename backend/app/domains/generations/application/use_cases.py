"""Generations use cases.

Two-phase flow so a slow provider call never holds a DB transaction:

  1. `StartGeneration` (inside the request transaction) — verify the
     provider is configured, **reserve credits**, and persist a pending
     `Generation`.
  2. The worker (slice-root `worker.py`, after the request commits) — call
     the provider with no transaction open, then in a fresh transaction run
     `FinalizeGeneration`: store the result and **capture** the hold, or
     mark the generation failed and **release** it.
"""

import logging
import uuid

from app.domains.credits.domain import CreditAction
from app.domains.generations.application.dtos import MediaDownload, MediaFileUrl
from app.domains.generations.application.ports import (
    ActivityTracker,
    CreditService,
    GenerationRepository,
    MediaStore,
    ProviderGateway,
)
from app.domains.generations.domain import (
    GENERATION_KINDS,
    Generation,
    GenerationFailed,
    GenerationNotFound,
    GenerationStatus,
    NotDeletable,
    ResultNotReady,
)

logger = logging.getLogger(__name__)


def _duration_ms(generation: Generation) -> int | None:
    """Accepted -> delivered wall time (queue wait + provider call)."""
    if generation.completed_at is None:
        return None
    return max(int((generation.completed_at - generation.created_at).total_seconds() * 1000), 0)


class StartGeneration:
    def __init__(
        self,
        generations: GenerationRepository,
        credits: CreditService,
        providers: ProviderGateway,
        analytics: ActivityTracker | None = None,
    ) -> None:
        self.generations = generations
        self.credits = credits
        self.providers = providers
        self.analytics = analytics

    async def execute(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None,
        kind: CreditAction,
        prompt: str,
    ) -> Generation:
        """Accept a generation job: hold credits and persist it as pending.
        The actual provider call happens in the worker."""
        if kind not in GENERATION_KINDS:
            raise GenerationFailed(f"'{kind.value}' is not a generation action.")
        self.providers.check_configured(kind)  # fail fast, before holding credits
        reservation = await self.credits.reserve(org_id, user_id, kind)
        generation = Generation(
            organization_id=org_id,
            user_id=user_id,
            kind=kind,
            model=self.providers.model_for(kind),
            prompt=prompt,
            reservation_id=reservation.id,
            credits_cost=reservation.amount,
        )
        await self.generations.add(generation)
        reservation.reference = f"generation:{generation.id}"
        if self.analytics:
            await self.analytics.capture_server_event(
                user_id,
                "generation_requested",
                {"kind": kind.value, "credits_cost": generation.credits_cost},
            )
        return generation


class FinalizeGeneration:
    """Persist the outcome and settle the credit hold atomically:
    success -> capture (charge sticks), failure -> release (refund)."""

    def __init__(
        self,
        generations: GenerationRepository,
        credits: CreditService,
        analytics: ActivityTracker | None = None,
    ) -> None:
        self.generations = generations
        self.credits = credits
        self.analytics = analytics

    async def execute(
        self,
        generation_id: uuid.UUID,
        *,
        file_path: str | None = None,
        mime_type: str | None = None,
        error: str | None = None,
    ) -> None:
        generation = await self.generations.get(generation_id)
        if generation is None:
            return
        if generation.status != GenerationStatus.PENDING:
            # Lost the race with a cancel (or a prior finalize): the hold was
            # already settled, so don't overwrite the status or touch credits.
            # The artifact is orthogonal to credit settlement, though — persist
            # it so a successful provider result isn't dropped just because the
            # row left PENDING first (e.g. a cancel that beat us by a hair).
            if error is None and file_path is not None and not generation.has_file:
                generation.file_path = file_path
                generation.mime_type = mime_type
            logger.info(
                "Generation %s already %s at finalize; persisted artifact, skipping settle.",
                generation_id,
                generation.status.value,
            )
            return
        if error is not None:
            generation.fail(error)
        else:
            generation.succeed(file_path, mime_type)
        if generation.reservation_id is not None:
            try:
                if error is not None:
                    await self.credits.release(
                        generation.reservation_id, reason="Generation failed — credits returned"
                    )
                else:
                    await self.credits.capture(generation.reservation_id)
            except Exception:
                # Never lose the generation result over a credit bookkeeping
                # error; the reservation will expire and self-correct.
                logger.exception(
                    "Could not settle reservation %s for generation %s",
                    generation.reservation_id,
                    generation_id,
                )
        # Only reached on the PENDING -> settled transition above, so a
        # redelivered job (acks_late) can't double-count the outcome.
        if self.analytics:
            if error is not None:
                await self.analytics.capture_server_event(
                    generation.user_id, "generation_failed", {"kind": generation.kind.value}
                )
            else:
                # The activation event (shared/events.toml).
                await self.analytics.capture_server_event(
                    generation.user_id,
                    "generation_completed",
                    {
                        "kind": generation.kind.value,
                        "credits_cost": generation.credits_cost,
                        "duration_ms": _duration_ms(generation),
                    },
                )


class CancelGeneration:
    """Cancel a still-pending generation and return its held credits."""

    def __init__(self, generations: GenerationRepository, credits: CreditService) -> None:
        self.generations = generations
        self.credits = credits

    async def execute(self, org_id: uuid.UUID, generation_id: uuid.UUID) -> Generation:
        generation = await self.generations.get_for_org(org_id, generation_id)
        if generation is None:
            raise GenerationNotFound("Generation not found.")
        generation.cancel()
        if generation.reservation_id is not None:
            await self.credits.release(
                generation.reservation_id, reason="Generation canceled — credits returned"
            )
        return generation


class DownloadGeneration:
    def __init__(self, generations: GenerationRepository, media: MediaStore) -> None:
        self.generations = generations
        self.media = media

    async def execute(self, org_id: uuid.UUID, generation_id: uuid.UUID) -> MediaDownload:
        generation = await self.generations.get_for_org(org_id, generation_id)
        if generation is None:
            raise GenerationNotFound("Generation not found.")
        if generation.file_path is None:
            raise ResultNotReady("This generation has no result file yet.")
        return await self.media.download(
            generation.file_path, generation.mime_type or "application/octet-stream"
        )


class GetGenerationFileUrl:
    def __init__(self, generations: GenerationRepository, media: MediaStore) -> None:
        self.generations = generations
        self.media = media

    async def execute(self, org_id: uuid.UUID, generation_id: uuid.UUID) -> MediaFileUrl:
        generation = await self.generations.get_for_org(org_id, generation_id)
        if generation is None:
            raise GenerationNotFound("Generation not found.")
        if generation.file_path is None:
            raise ResultNotReady("This generation has no result file yet.")
        return await self.media.file_url(generation.file_path)


class DeleteGeneration:
    """Delete a settled generation and best-effort remove its result file."""

    def __init__(self, generations: GenerationRepository, media: MediaStore) -> None:
        self.generations = generations
        self.media = media

    async def execute(self, org_id: uuid.UUID, generation_id: uuid.UUID) -> None:
        generation = await self.generations.get_for_org(org_id, generation_id)
        if generation is None:
            raise GenerationNotFound("Generation not found.")
        if not generation.is_settled:
            raise NotDeletable("This generation can't be deleted while it's still running.")
        if generation.file_path is not None:
            try:
                await self.media.delete(generation.file_path)
            except Exception as exc:
                # Do not log SDK exception chains, which may contain signed URLs.
                logger.warning(
                    "Could not delete media for generation %s (%s)",
                    generation_id,
                    type(exc).__name__,
                )
        await self.generations.remove(generation)
