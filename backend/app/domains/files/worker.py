"""Bounded pending-upload sweep with a separate transaction per file."""

import logging
from datetime import UTC, datetime, timedelta

from app.core.database import SessionLocal
from app.core.policy import UPLOAD_PENDING_TTL_HOURS
from app.domains.files.infrastructure.repositories import SqlAlchemyFileRepository
from app.domains.files.interface.deps import build_pending_upload_cleanup

logger = logging.getLogger(__name__)
SWEEP_BATCH_SIZE = 500


async def sweep_stale_uploads() -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=UPLOAD_PENDING_TTL_HOURS)
    async with SessionLocal() as session:
        ids = await SqlAlchemyFileRepository(session).stale_pending_ids(cutoff, SWEEP_BATCH_SIZE)
    deleted = failed = 0
    for file_id in ids:
        try:
            async with SessionLocal() as session:
                async with session.begin():
                    removed = await build_pending_upload_cleanup(session).execute(file_id, cutoff)
            deleted += int(removed)
        except Exception as exc:
            failed += 1
            logger.warning("Pending file cleanup failed: %s", type(exc).__name__)
    logger.info("Pending file cleanup: scanned=%d deleted=%d failed=%d", len(ids), deleted, failed)
    return deleted
