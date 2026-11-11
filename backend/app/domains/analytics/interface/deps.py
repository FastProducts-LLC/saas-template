"""Analytics composition root.

`build_activity_tracker` is what other slices' composition roots (request
deps and worker entry points alike) call to obtain the server-event writer;
it satisfies their slice-local `ActivityTracker` ports structurally.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.analytics.application import use_cases as uc
from app.domains.analytics.domain.policy import INGEST_EVENTS_PER_MINUTE
from app.domains.analytics.infrastructure.rate_gate import RedisIngestRateGate
from app.domains.analytics.infrastructure.repositories import SqlAlchemyActivityEventRepository

DB = Annotated[AsyncSession, Depends(get_db)]

_gate = RedisIngestRateGate(per_minute=INGEST_EVENTS_PER_MINUTE)


def get_record_client_event(db: DB) -> uc.RecordClientEvent:
    return uc.RecordClientEvent(SqlAlchemyActivityEventRepository(db), _gate)


def build_activity_tracker(session: AsyncSession) -> uc.CaptureServerEvent:
    """Server-event writer bound to the caller's session/transaction."""
    return uc.CaptureServerEvent(SqlAlchemyActivityEventRepository(session))
