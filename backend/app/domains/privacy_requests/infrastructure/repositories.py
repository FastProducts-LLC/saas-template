"""Privacy-request repository."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.privacy_requests.infrastructure.orm  # noqa: F401
from app.domains.privacy_requests.domain import PrivacyRequest
from app.domains.privacy_requests.domain.entities import PrivacyRequestStatus


class SqlAlchemyPrivacyRequestRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, request: PrivacyRequest) -> None:
        self.db.add(request)
        await self.db.flush()

    async def get(self, request_id: uuid.UUID) -> PrivacyRequest | None:
        return await self.db.get(PrivacyRequest, request_id)

    async def list_requests(
        self,
        *,
        status: PrivacyRequestStatus | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[PrivacyRequest], int]:
        filters = []
        if status is not None:
            filters.append(PrivacyRequest.status == status)

        count_stmt = select(func.count()).select_from(PrivacyRequest)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = select(PrivacyRequest)
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(PrivacyRequest.created_at.desc(), PrivacyRequest.id)
            .limit(limit)
            .offset(offset)
        )
        items = list((await self.db.execute(stmt)).scalars())
        return items, total

    async def list_payload_purge_candidates(self, older_than: datetime) -> list[PrivacyRequest]:
        stmt = select(PrivacyRequest).where(
            PrivacyRequest.payload_purged_at.is_(None),
            PrivacyRequest.created_at < older_than,
        )
        return list((await self.db.execute(stmt)).scalars())
