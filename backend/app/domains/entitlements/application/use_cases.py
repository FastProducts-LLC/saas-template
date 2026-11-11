"""Resolve plan limits, reserve capacity, and manage administrator overrides."""

import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime

from app.domains.audit.domain import AuditEvent, actions
from app.domains.entitlements.application.dtos import EntitlementSnapshot, EntitlementUsage
from app.domains.entitlements.application.ports import (
    ApiKeyCounter,
    AuditRecorder,
    OverrideRepository,
    PlanReader,
    SeatCounter,
    SerializationLock,
)
from app.domains.entitlements.domain import (
    EntitlementKey,
    EntitlementLimitReached,
    EntitlementOverride,
    EntitlementRequired,
    is_included,
    resolve_limit,
    within_limit,
)


class EntitlementService:
    def __init__(
        self, overrides: OverrideRepository, plans: PlanReader, locks: SerializationLock
    ) -> None:
        self.overrides = overrides
        self.plans = plans
        self.locks = locks

    async def limit_for(self, org_id: uuid.UUID, key: EntitlementKey) -> int | None:
        return resolve_limit(
            await self.plans.plan_for(org_id), key, await self.overrides.get(org_id, key)
        )

    async def ensure_included(self, org_id: uuid.UUID, key: EntitlementKey) -> None:
        if not is_included(await self.limit_for(org_id, key)):
            raise EntitlementRequired(f"The organization does not include '{key.value}'.")

    async def ensure_within_limit(
        self, org_id: uuid.UUID, key: EntitlementKey, count: Callable[[], Awaitable[int]]
    ) -> None:
        if await self.limit_for(org_id, key) is None:
            return
        await self.locks.acquire(org_id, key)
        # An override may have changed while waiting for the previous transaction.
        limit = await self.limit_for(org_id, key)
        if limit is None:
            return
        if not within_limit(limit, await count()):
            raise EntitlementLimitReached(
                f"The organization has reached its '{key.value}' limit.",
                params={"limit": limit, "resource": key.label},
            )

    async def snapshot(
        self, org_id: uuid.UUID, usage: Mapping[EntitlementKey, int]
    ) -> EntitlementSnapshot:
        plan = await self.plans.plan_for(org_id)
        overrides = {row.key: row for row in await self.list_overrides(org_id)}
        now = datetime.now(UTC)
        entries = []
        for key in EntitlementKey:
            override = overrides.get(key)
            active = override is not None and override.is_active(now)
            limit = resolve_limit(plan, key, override, now=now)
            entries.append(
                EntitlementUsage(
                    key=key,
                    limit=limit,
                    used=usage.get(key, 0),
                    included=is_included(limit),
                    source="override" if active else "plan",
                    expires_at=override.expires_at if active else None,
                )
            )
        return EntitlementSnapshot(plan=plan, entitlements=entries)

    async def list_overrides(self, org_id: uuid.UUID) -> list[EntitlementOverride]:
        return await self.overrides.list_for_org(org_id)

    async def upsert_override(
        self,
        org_id: uuid.UUID,
        key: EntitlementKey,
        limit_value: int | None,
        *,
        actor_id: uuid.UUID,
        expires_at: datetime | None = None,
        note: str | None = None,
    ) -> tuple[EntitlementOverride, int | None]:
        await self.locks.acquire(org_id, key)
        previous = await self.overrides.get(org_id, key)
        old_limit = previous.limit_value if previous is not None else None
        override = await self.overrides.upsert(
            EntitlementOverride(
                organization_id=org_id,
                key=key,
                limit_value=limit_value,
                created_by_id=actor_id,
                expires_at=expires_at,
                note=note,
            )
        )
        return override, old_limit

    async def delete_override(
        self, org_id: uuid.UUID, key: EntitlementKey
    ) -> EntitlementOverride | None:
        await self.locks.acquire(org_id, key)
        override = await self.overrides.get(org_id, key)
        if override is not None:
            await self.overrides.delete(override)
        return override


class GetEntitlementSnapshot:
    def __init__(
        self, service: EntitlementService, seats: SeatCounter, api_keys: ApiKeyCounter
    ) -> None:
        self.service = service
        self.seats = seats
        self.api_keys = api_keys

    async def execute(self, org_id: uuid.UUID) -> EntitlementSnapshot:
        return await self.service.snapshot(
            org_id,
            {
                EntitlementKey.SEATS: await self.seats.count_seats(org_id),
                EntitlementKey.API_KEYS: await self.api_keys.count_active(org_id),
            },
        )


class ManageOverrides:
    def __init__(self, service: EntitlementService, audit: AuditRecorder) -> None:
        self.service = service
        self.audit = audit

    async def upsert(
        self,
        org_id: uuid.UUID,
        key: EntitlementKey,
        limit_value: int | None,
        *,
        actor_id: uuid.UUID,
        expires_at: datetime | None = None,
        note: str | None = None,
    ) -> EntitlementOverride:
        override, old_limit = await self.service.upsert_override(
            org_id,
            key,
            limit_value,
            actor_id=actor_id,
            expires_at=expires_at,
            note=note,
        )
        await self.audit.record(
            AuditEvent(
                action=actions.ENTITLEMENT_OVERRIDE_SET,
                actor_user_id=actor_id,
                organization_id=org_id,
                target_type="entitlement",
                target_id=override.id,
                meta={"key": key.value, "old_limit": old_limit, "new_limit": limit_value},
            )
        )
        return override

    async def delete(self, org_id: uuid.UUID, key: EntitlementKey, *, actor_id: uuid.UUID) -> None:
        override = await self.service.delete_override(org_id, key)
        if override is not None:
            await self.audit.record(
                AuditEvent(
                    action=actions.ENTITLEMENT_OVERRIDE_REMOVED,
                    actor_user_id=actor_id,
                    organization_id=org_id,
                    target_type="entitlement",
                    target_id=override.id,
                    meta={"key": key.value, "old_limit": override.limit_value},
                )
            )
