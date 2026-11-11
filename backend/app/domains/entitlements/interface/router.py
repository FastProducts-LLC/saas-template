"""Member snapshots and superuser override management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.entitlements.application.use_cases import (
    EntitlementService,
    GetEntitlementSnapshot,
    ManageOverrides,
)
from app.domains.entitlements.domain import EntitlementKey, UnknownEntitlementKey
from app.domains.entitlements.interface.deps import (
    get_entitlement_service,
    get_entitlement_snapshot,
    get_manage_overrides,
)
from app.domains.entitlements.interface.schemas import (
    AdminSnapshotOut,
    OverrideOut,
    OverrideUpdate,
    SnapshotOut,
)
from app.domains.organizations.interface.deps import CurrentMember, OrgQueriesDep

router = APIRouter(tags=["entitlements"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])
Snapshots = Annotated[GetEntitlementSnapshot, Depends(get_entitlement_snapshot)]
Service = Annotated[EntitlementService, Depends(get_entitlement_service)]
Overrides = Annotated[ManageOverrides, Depends(get_manage_overrides)]


def _key(key: str) -> EntitlementKey:
    try:
        return EntitlementKey(key)
    except ValueError:
        raise UnknownEntitlementKey("Unknown entitlement key.") from None


@router.get("/orgs/{org_id}/entitlements", response_model=SnapshotOut)
async def get_snapshot(membership: CurrentMember, snapshots: Snapshots):
    return await snapshots.execute(membership.organization_id)


@admin_router.get("/organizations/{org_id}/entitlements", response_model=AdminSnapshotOut)
async def get_admin_snapshot(
    org_id: uuid.UUID,
    user: CurrentSuperuser,
    orgs: OrgQueriesDep,
    snapshots: Snapshots,
    service: Service,
):
    await orgs.get_org(org_id)
    snapshot = await snapshots.execute(org_id)
    return AdminSnapshotOut(
        **SnapshotOut.model_validate(snapshot).model_dump(),
        overrides=[OverrideOut.model_validate(row) for row in await service.list_overrides(org_id)],
    )


@admin_router.put("/organizations/{org_id}/entitlements/{key}", response_model=OverrideOut)
async def set_override(
    org_id: uuid.UUID,
    key: str,
    payload: OverrideUpdate,
    user: CurrentSuperuser,
    orgs: OrgQueriesDep,
    overrides: Overrides,
):
    entitlement_key = _key(key)
    await orgs.get_org(org_id)
    return await overrides.upsert(
        org_id,
        entitlement_key,
        payload.limit_value,
        actor_id=user.id,
        expires_at=payload.expires_at,
        note=payload.note,
    )


@admin_router.delete(
    "/organizations/{org_id}/entitlements/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_override(
    org_id: uuid.UUID,
    key: str,
    user: CurrentSuperuser,
    orgs: OrgQueriesDep,
    overrides: Overrides,
):
    entitlement_key = _key(key)
    await orgs.get_org(org_id)
    await overrides.delete(org_id, entitlement_key, actor_id=user.id)
