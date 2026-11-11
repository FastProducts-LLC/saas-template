"""Cross-slice credits facade.

Wrap any metered call (LLM / image / video generation) so credits are held
up-front and only charged once a result is actually produced:

    engine = build_credit_engine(db)   # from credits interface.deps
    async with hold_credits(engine, org_id=org.id, user_id=user.id,
                            action=CreditAction.LLM_CALL, reference="...") :
        result = await call_the_model(...)
    # exited normally -> hold captured; raised -> hold released

Flows that span transactions (e.g. background jobs) should instead call
`CreditEngine.reserve(...)` in the request and `capture`/`release` from the
job with its own session.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.domains.credits.application.use_cases import CreditEngine
from app.domains.credits.domain import CreditAction, CreditReservation

__all__ = ["hold_credits"]


@asynccontextmanager
async def hold_credits(
    engine: CreditEngine,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: CreditAction,
    reference: str | None = None,
    api_key_id: uuid.UUID | None = None,
) -> AsyncIterator[CreditReservation]:
    reservation = await engine.reserve(
        org_id, user_id, action, reference=reference, api_key_id=api_key_id
    )
    try:
        yield reservation
    except BaseException:
        await engine.release(reservation.id)
        raise
    else:
        await engine.capture(reservation.id)
