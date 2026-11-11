"""Organizations HTTP endpoints — thin: parse → use case/query → serialize."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domains.auth.interface.deps import CurrentUser, CurrentVerifiedUser
from app.domains.organizations.application import use_cases as uc
from app.domains.organizations.application.queries import OrgQueries
from app.domains.organizations.interface.deps import (
    CurrentAdmin,
    CurrentMember,
    CurrentOwner,
    get_accept_invitation,
    get_change_member_role,
    get_create_org,
    get_delete_org,
    get_invite_member,
    get_org_queries,
    get_remove_member,
    get_rename_org,
    get_revoke_invitation,
    get_set_org_domain,
)
from app.domains.organizations.interface.schemas import (
    AcceptInviteRequest,
    InvitationOut,
    InviteCreate,
    MemberOut,
    OrgCreate,
    OrgDomainUpdate,
    OrgUpdate,
    OrgWithRole,
    RoleUpdate,
)

router = APIRouter(tags=["organizations"])

Queries = Annotated[OrgQueries, Depends(get_org_queries)]


def _org_with_role(org, membership) -> OrgWithRole:
    return OrgWithRole(
        id=org.id,
        name=org.name,
        slug=org.slug,
        email_domain=org.email_domain,
        created_at=org.created_at,
        role=membership.role,
    )


def _member_out(membership, user) -> MemberOut:
    return MemberOut(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.post("/orgs", response_model=OrgWithRole, status_code=status.HTTP_201_CREATED)
async def create_org(
    payload: OrgCreate,
    user: CurrentVerifiedUser,
    use_case: Annotated[uc.CreateOrganization, Depends(get_create_org)],
):
    org, membership = await use_case.execute(user, payload.name, payload.intended_use)
    return _org_with_role(org, membership)


@router.get("/orgs", response_model=list[OrgWithRole])
async def list_my_orgs(user: CurrentUser, queries: Queries):
    rows = await queries.list_user_orgs(user.id)
    return [_org_with_role(org, m) for org, m in rows]


@router.get("/orgs/{org_id}", response_model=OrgWithRole)
async def get_org(membership: CurrentMember, queries: Queries):
    org = await queries.get_org(membership.organization_id)
    return _org_with_role(org, membership)


@router.patch("/orgs/{org_id}", response_model=OrgWithRole)
async def update_org(
    payload: OrgUpdate,
    membership: CurrentAdmin,
    queries: Queries,
    use_case: Annotated[uc.RenameOrganization, Depends(get_rename_org)],
):
    org = await queries.get_org(membership.organization_id)
    org = await use_case.execute(org, payload.name)
    return _org_with_role(org, membership)


@router.put("/orgs/{org_id}/domain", response_model=OrgWithRole)
async def set_org_domain(
    payload: OrgDomainUpdate,
    membership: CurrentOwner,
    user: CurrentVerifiedUser,
    queries: Queries,
    use_case: Annotated[uc.SetOrgDomain, Depends(get_set_org_domain)],
):
    org = await queries.get_org(membership.organization_id)
    org = await use_case.execute(org, user, payload.domain)
    return _org_with_role(org, membership)


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    membership: CurrentOwner,
    queries: Queries,
    use_case: Annotated[uc.DeleteOrganization, Depends(get_delete_org)],
):
    org = await queries.get_org(membership.organization_id)
    await use_case.execute(org)


# -- members ------------------------------------------------------------------


@router.get("/orgs/{org_id}/members", response_model=list[MemberOut])
async def list_members(membership: CurrentMember, queries: Queries):
    rows = await queries.list_members(membership.organization_id)
    return [_member_out(m, u) for m, u in rows]


@router.patch("/orgs/{org_id}/members/{membership_id}", response_model=MemberOut)
async def change_member_role(
    membership_id: uuid.UUID,
    payload: RoleUpdate,
    membership: CurrentAdmin,
    queries: Queries,
    use_case: Annotated[uc.ChangeMemberRole, Depends(get_change_member_role)],
):
    target = await use_case.execute(membership, membership_id, payload.role)
    return _member_out(*await queries.get_member(target))


@router.delete("/orgs/{org_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    membership_id: uuid.UUID,
    membership: CurrentMember,
    use_case: Annotated[uc.RemoveMember, Depends(get_remove_member)],
):
    await use_case.execute(membership, membership_id)


# -- invitations ----------------------------------------------------------------


@router.post(
    "/orgs/{org_id}/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    payload: InviteCreate,
    membership: CurrentAdmin,
    user: CurrentVerifiedUser,
    queries: Queries,
    use_case: Annotated[uc.InviteMember, Depends(get_invite_member)],
):
    org = await queries.get_org(membership.organization_id)
    return await use_case.execute(org, user, payload.email, payload.role)


@router.get("/orgs/{org_id}/invitations", response_model=list[InvitationOut])
async def list_invitations(membership: CurrentAdmin, queries: Queries):
    return await queries.list_pending_invitations(membership.organization_id)


@router.delete("/orgs/{org_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    membership: CurrentAdmin,
    use_case: Annotated[uc.RevokeInvitation, Depends(get_revoke_invitation)],
):
    await use_case.execute(membership.organization_id, invitation_id)


@router.post("/invitations/accept", response_model=OrgWithRole)
async def accept_invitation(
    payload: AcceptInviteRequest,
    user: CurrentUser,
    use_case: Annotated[uc.AcceptInvitation, Depends(get_accept_invitation)],
):
    org, membership = await use_case.execute(user, payload.token)
    return _org_with_role(org, membership)
