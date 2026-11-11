"""Entitlement composition root and reusable route gate for application forks."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.audit.interface.deps import get_audit_recorder
from app.domains.entitlements.application.ports import AuditRecorder
from app.domains.entitlements.application.use_cases import (
    EntitlementService,
    GetEntitlementSnapshot,
    ManageOverrides,
)
from app.domains.entitlements.domain import EntitlementKey
from app.domains.entitlements.infrastructure.repositories import (
    PostgresEntitlementLock,
    SqlAlchemyOverrideRepository,
)

DB = Annotated[AsyncSession, Depends(get_db)]


def build_entitlement_service(db: AsyncSession) -> EntitlementService:
    """Build the service for a use-case gate using the caller's transaction.

    Inject this through a slice-local checker Protocol. Call ensure_within_limit
    before writing a capacity-consuming row in the same transaction; the lock
    remains held until get_db commits or rolls back. Services never commit.
    """
    from app.domains.billing.interface.deps import build_plan_reader

    return EntitlementService(
        SqlAlchemyOverrideRepository(db),
        build_plan_reader(db),
        PostgresEntitlementLock(db),
    )


def get_entitlement_service(db: DB) -> EntitlementService:
    return build_entitlement_service(db)


def get_entitlement_snapshot(db: DB) -> GetEntitlementSnapshot:
    from app.domains.api_keys.interface.deps import build_api_key_counter
    from app.domains.organizations.interface.deps import build_seat_counter

    return GetEntitlementSnapshot(
        build_entitlement_service(db),
        build_seat_counter(db),
        build_api_key_counter(db),
    )


def get_manage_overrides(
    db: DB,
    audit: Annotated[AuditRecorder, Depends(get_audit_recorder)],
) -> ManageOverrides:
    return ManageOverrides(build_entitlement_service(db), audit)


def require_entitlement(key: EntitlementKey):
    """Gate an /orgs/{org_id}/… route with the same syntax as require_feature.

    Use dependencies=[require_entitlement(EntitlementKey.SEATS)]. Membership
    resolves the tenant before ensure_included runs; a zero limit raises
    EntitlementRequired. Capacity-consuming writes must also use the service's
    ensure_within_limit in their use case, with the same request transaction.
    """
    from app.domains.organizations.interface.deps import CurrentMember

    async def dependency(membership: CurrentMember, db: DB) -> None:
        await build_entitlement_service(db).ensure_included(membership.organization_id, key)

    return Depends(dependency)
