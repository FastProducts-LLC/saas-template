"""Ports consumed by entitlement services; adapters share the request transaction."""

import uuid
from typing import Protocol

from app.domains.audit.domain import AuditEvent
from app.domains.billing.domain import Plan
from app.domains.entitlements.domain import EntitlementKey, EntitlementOverride


class OverrideRepository(Protocol):
    async def get(self, org_id: uuid.UUID, key: EntitlementKey) -> EntitlementOverride | None: ...

    async def list_for_org(self, org_id: uuid.UUID) -> list[EntitlementOverride]: ...

    async def upsert(self, override: EntitlementOverride) -> EntitlementOverride: ...

    async def delete(self, override: EntitlementOverride) -> None: ...


class PlanReader(Protocol):
    async def plan_for(self, org_id: uuid.UUID) -> Plan: ...


class SerializationLock(Protocol):
    async def acquire(self, org_id: uuid.UUID, key: EntitlementKey) -> None:
        """Hold an org/key lock until the enclosing transaction ends."""
        ...


class SeatCounter(Protocol):
    async def count_seats(self, org_id: uuid.UUID) -> int: ...


class ApiKeyCounter(Protocol):
    async def count_active(self, org_id: uuid.UUID) -> int: ...


class AuditRecorder(Protocol):
    async def record(self, event: AuditEvent) -> None: ...
