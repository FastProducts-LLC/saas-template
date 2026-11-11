"""Credits background jobs — the composition root (no request context).

The sweep complements the engine's lazy settlement: holds normally expire on
the org's next wallet touch, but a dormant org whose worker died mid-action
would otherwise keep credits held indefinitely. Each org settles in its own
transaction so one contended wallet can't stall or roll back the batch.
"""

import logging
from datetime import UTC, datetime

from app.core.database import SessionLocal
from app.domains.credits.infrastructure.repositories import SqlAlchemyReservationRepository
from app.domains.credits.interface.deps import build_credit_engine

logger = logging.getLogger(__name__)


async def sweep_stale_reservations() -> int:
    """Refund expired pending holds across all orgs; returns orgs settled."""
    async with SessionLocal() as session:
        org_ids = await SqlAlchemyReservationRepository(session).list_orgs_with_stale_pending(
            datetime.now(UTC)
        )
    for org_id in org_ids:
        async with SessionLocal() as session:
            async with session.begin():
                await build_credit_engine(session).settle(org_id)
    if org_ids:
        logger.info("Expired stale credit holds for %d org(s)", len(org_ids))
    return len(org_ids)
