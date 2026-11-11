"""Tenant-scoped overrides and PostgreSQL transaction-scoped capacity locks."""

import hashlib
import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.entitlements.domain import EntitlementKey, EntitlementOverride
from app.domains.entitlements.infrastructure.orm import organization_entitlements_table


class SqlAlchemyOverrideRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, org_id: uuid.UUID, key: EntitlementKey) -> EntitlementOverride | None:
        return (
            await self.db.execute(
                select(EntitlementOverride)
                .where(
                    EntitlementOverride.organization_id == org_id,
                    EntitlementOverride.key == key,
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def list_for_org(self, org_id: uuid.UUID) -> list[EntitlementOverride]:
        return list(
            (
                await self.db.execute(
                    select(EntitlementOverride)
                    .where(
                        EntitlementOverride.organization_id == org_id,
                    )
                    .order_by(EntitlementOverride.key)
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        )

    async def upsert(self, override: EntitlementOverride) -> EntitlementOverride:
        values = {
            column.name: getattr(override, column.name)
            for column in organization_entitlements_table.columns
        }
        stmt = insert(EntitlementOverride).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_organization_entitlements_org_key",
            set_={
                name: getattr(stmt.excluded, name)
                for name in (
                    "limit_value",
                    "source",
                    "note",
                    "expires_at",
                    "updated_at",
                )
            },
        ).returning(EntitlementOverride)
        return (await self.db.execute(stmt.execution_options(populate_existing=True))).scalar_one()

    async def delete(self, override: EntitlementOverride) -> None:
        await self.db.delete(override)
        await self.db.flush()


class PostgresEntitlementLock:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def acquire(self, org_id: uuid.UUID, key: EntitlementKey) -> None:
        # Stable across processes; namespaced so unrelated advisory locks do not overlap.
        digest = hashlib.sha256(f"entitlements:{org_id}:{key.value}".encode()).digest()
        lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
