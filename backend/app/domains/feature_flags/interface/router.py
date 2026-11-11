"""Public config + superuser feature-flag endpoints.

GET /config is the unauthenticated client bootstrap: which optional modules
are on. Toggling is superuser-only under /admin/flags.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.feature_flags.application import use_cases as uc
from app.domains.feature_flags.interface.deps import (
    get_list_feature_flags,
    get_public_config,
    get_set_feature_flag,
)
from app.domains.feature_flags.interface.schemas import (
    AdminFeatureFlagList,
    AdminFeatureFlagOut,
    FeatureFlagSet,
    PublicConfigOut,
)

public_router = APIRouter(tags=["config"])

admin_router = APIRouter(prefix="/admin/flags", tags=["admin-flags"])


@public_router.get("/config", response_model=PublicConfigOut)
async def get_config(
    use_case: Annotated[uc.GetPublicConfig, Depends(get_public_config)],
):
    return PublicConfigOut(features=await use_case.execute())


@admin_router.get("", response_model=AdminFeatureFlagList)
async def list_flags(
    _: CurrentSuperuser,
    use_case: Annotated[uc.ListFeatureFlags, Depends(get_list_feature_flags)],
):
    return AdminFeatureFlagList(
        items=[
            AdminFeatureFlagOut.from_state(key, enabled, row)
            for key, enabled, row in await use_case.execute()
        ]
    )


@admin_router.put("/{key}", response_model=AdminFeatureFlagOut)
async def set_flag(
    key: str,
    body: FeatureFlagSet,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.SetFeatureFlag, Depends(get_set_feature_flag)],
):
    flag = await use_case.execute(key, enabled=body.enabled, by=admin.id)
    return AdminFeatureFlagOut.from_state(flag.key, flag.enabled, flag)
