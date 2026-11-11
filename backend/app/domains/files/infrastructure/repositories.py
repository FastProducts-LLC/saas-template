"""Stored-file persistence; owner bulk operations are always scoped."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.domain import User
from app.domains.files.domain.entities import FilePurpose, StoredFile, StoredFileStatus
from app.domains.files.infrastructure.orm import stored_files_table


class SqlAlchemyFileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def lock_owner(self, user_id: uuid.UUID) -> None:
        # Lock an existing owner even when they have no files yet. Every upload
        # create/confirm and owner cleanup takes this lock before file-row locks.
        # Avoid flushing a changed community profile before acquiring the lock.
        with self.db.no_autoflush:
            await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())

    async def list_for_owner(self, user_id: uuid.UUID, purpose: FilePurpose) -> list[StoredFile]:
        stmt = (
            select(StoredFile)
            .where(
                stored_files_table.c.user_id == user_id,
                stored_files_table.c.purpose == purpose,
            )
            .execution_options(populate_existing=True)
        )
        return list((await self.db.scalars(stmt)).all())

    async def add(self, file: StoredFile) -> None:
        self.db.add(file)
        await self.db.flush()

    async def get(self, file_id: uuid.UUID, *, lock: bool = False) -> StoredFile | None:
        stmt = select(StoredFile).where(stored_files_table.c.id == file_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def delete(self, file: StoredFile) -> None:
        await self.db.delete(file)
        await self.db.flush()

    async def list_for_user(self, user_id: uuid.UUID) -> list[StoredFile]:
        stmt = select(StoredFile).where(stored_files_table.c.user_id == user_id)
        return list((await self.db.scalars(stmt)).all())

    async def list_for_org(self, org_id: uuid.UUID) -> list[StoredFile]:
        stmt = select(StoredFile).where(stored_files_table.c.organization_id == org_id)
        return list((await self.db.scalars(stmt)).all())

    async def stale_pending_ids(self, cutoff: datetime, limit: int) -> list[uuid.UUID]:
        stmt = (
            select(stored_files_table.c.id)
            .where(
                stored_files_table.c.status == StoredFileStatus.PENDING,
                stored_files_table.c.created_at < cutoff,
            )
            .order_by(stored_files_table.c.created_at, stored_files_table.c.id)
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())
