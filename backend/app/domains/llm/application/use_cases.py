"""LLM use cases.

Two-phase flow so a slow provider call never holds a DB transaction:

  1. `StartLlmCall` (inside the request transaction) — verify the provider
     is configured, **reserve credits**, and persist a pending `LlmCall`.
  2. The worker (slice-root `worker.py`, after the request commits) — call
     the provider with no transaction open, then in a fresh transaction run
     `FinalizeLlmCall`: store the result and **capture** the hold, or mark
     the call failed and **release** it.
"""

import logging
import uuid

from app.domains.credits.domain import CreditAction
from app.domains.llm.application.ports import (
    ActivityTracker,
    CreditService,
    LlmCallRepository,
    LlmGateway,
)
from app.domains.llm.domain.entities import LlmCall, LlmProvider, LlmResult

logger = logging.getLogger(__name__)


class StartLlmCall:
    def __init__(
        self,
        calls: LlmCallRepository,
        credits: CreditService,
        gateway: LlmGateway,
    ) -> None:
        self.calls = calls
        self.credits = credits
        self.gateway = gateway

    async def execute(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None,
        provider: LlmProvider,
        prompt: str,
        max_tokens: int,
    ) -> LlmCall:
        """Accept a completion job: hold credits and persist it as pending.
        The actual provider call happens in the worker."""
        self.gateway.check_configured(provider)  # fail fast, before holding credits
        model = self.gateway.model_for(provider)
        reservation = await self.credits.reserve(
            org_id, user_id, CreditAction.LLM_CALL, reference=f"llm:{provider.value}"
        )
        call = LlmCall.pending(
            organization_id=org_id,
            user_id=user_id,
            provider=provider,
            model=model,
            prompt=prompt,
            reservation_id=reservation.id,
            credits_cost=reservation.amount,
        )
        await self.calls.add(call)
        reservation.reference = f"llm:{call.id}"
        return call


class FinalizeLlmCall:
    """Persist the outcome and settle the credit hold atomically:
    success -> capture (charge sticks), failure -> release (refund)."""

    def __init__(
        self,
        calls: LlmCallRepository,
        credits: CreditService,
        analytics: ActivityTracker | None = None,
    ) -> None:
        self.calls = calls
        self.credits = credits
        self.analytics = analytics

    async def execute(
        self,
        call_id: uuid.UUID,
        *,
        result: LlmResult | None = None,
        error: str | None = None,
    ) -> None:
        call = await self.calls.get(call_id)
        if call is None:
            return
        if not call.is_pending:
            logger.info(
                "LlmCall %s already %s at finalize; skipping settle.", call_id, call.status.value
            )
            return
        if error is not None:
            call.fail(error)
        else:
            assert result is not None  # noqa: S101 — invariant: no error implies a result
            call.succeed(result)
        if call.reservation_id is not None:
            try:
                if error is not None:
                    await self.credits.release(
                        call.reservation_id, reason="LLM call failed — credits returned"
                    )
                else:
                    await self.credits.capture(call.reservation_id)
            except Exception:
                logger.exception(
                    "Could not settle reservation %s for llm call %s",
                    call.reservation_id,
                    call_id,
                )
        # Only reached on the pending -> settled transition (redelivery-safe).
        if self.analytics and error is None:
            await self.analytics.capture_server_event(
                call.user_id,
                "llm_call_completed",
                {"provider": call.provider.value, "credits_cost": call.credits_cost},
            )
