"""API keys HTTP endpoints — thin: parse → use case → serialize."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domains.api_keys.application import use_cases as uc
from app.domains.api_keys.interface.deps import (
    get_create_api_key,
    get_list_api_keys,
    get_revoke_api_key,
)
from app.domains.api_keys.interface.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.domains.auth.interface.deps import CurrentVerifiedUser, NoImpersonation
from app.domains.organizations.interface.deps import CurrentAdmin, CurrentMember

router = APIRouter(tags=["api-keys"])


@router.post(
    "/orgs/{org_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    # An impersonating admin must not mint a key that outlives the session.
    dependencies=[NoImpersonation],
)
async def create_api_key(
    org_id: uuid.UUID,
    payload: ApiKeyCreate,
    membership: CurrentAdmin,
    _user: CurrentVerifiedUser,
    use_case: Annotated[uc.CreateApiKey, Depends(get_create_api_key)],
):
    key, raw = await use_case.execute(
        org_id=org_id,
        user_id=membership.user_id,
        name=payload.name,
    )
    return ApiKeyCreated(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        raw_key=raw,
    )


@router.get("/orgs/{org_id}/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    org_id: uuid.UUID,
    membership: CurrentMember,
    use_case: Annotated[uc.ListApiKeys, Depends(get_list_api_keys)],
):
    return await use_case.execute(org_id)


@router.delete(
    "/orgs/{org_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    membership: CurrentAdmin,
    _user: CurrentVerifiedUser,
    use_case: Annotated[uc.RevokeApiKey, Depends(get_revoke_api_key)],
):
    await use_case.execute(org_id, key_id)
