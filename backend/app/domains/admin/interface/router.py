"""Admin HTTP endpoints — superuser only.

Every route hangs off the `CurrentSuperuser` dependency; nothing here is
tenant-scoped, so the 403 on non-superusers is the only access control.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.error_handling import lookup_error_context
from app.core.policy import ADMIN_PAGE_SIZE, ERROR_CONTEXT_RETENTION_DAYS
from app.domains.admin.application import use_cases as uc
from app.domains.admin.domain import AdminErrorRecordNotFound, AdminOrgNotFound
from app.domains.admin.infrastructure.repositories import SqlAlchemyAdminRepository
from app.domains.admin.interface.deps import (
    CurrentSuperuser,
    get_adjust_org_credits,
    get_admin_repository,
    get_analytics,
    get_impersonate_user,
    get_merge_organizations,
    get_platform_stats,
    get_revoke_invitation,
    get_set_org_suspended,
    get_set_user_active,
    get_signout_user_everywhere,
)
from app.domains.admin.interface.schemas import (
    AdminAnalyticsOut,
    AdminAuditOut,
    AdminCustomerUsageOut,
    AdminGenerationOut,
    AdminInvitationOut,
    AdminOrgMemberOut,
    AdminOrgOut,
    AdminOrgSuspensionOut,
    AdminStats,
    AdminUserOut,
    AdminWalletOut,
    CreditAdjustRequest,
    ImpersonationOut,
    MergeOrgsOut,
    MergeOrgsRequest,
    Page,
)
from app.domains.auth.domain import User
from app.domains.credits.domain import CreditAction
from app.domains.generations.domain import GenerationStatus
from app.domains.organizations.interface.deps import OrgQueriesDep

router = APIRouter(prefix="/admin", tags=["admin"])

Repo = Annotated[SqlAlchemyAdminRepository, Depends(get_admin_repository)]
SearchParam = Annotated[str, Query(max_length=320)]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


def _user_out(user: User, org_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        organization_count=org_count,
    )


@router.get("/stats", response_model=AdminStats)
async def get_stats(
    _: CurrentSuperuser, use_case: Annotated[uc.GetPlatformStats, Depends(get_platform_stats)]
):
    return AdminStats.model_validate(await use_case.execute())


@router.get("/analytics", response_model=AdminAnalyticsOut)
async def get_analytics(
    _: CurrentSuperuser, use_case: Annotated[uc.GetAnalytics, Depends(get_analytics)]
):
    """Aggregated platform analytics for the admin overview dashboard."""
    return AdminAnalyticsOut.model_validate(await use_case.execute())


# -- organizations -------------------------------------------------------------


@router.get("/organizations", response_model=Page[AdminOrgOut])
async def list_organizations(
    _: CurrentSuperuser,
    repo: Repo,
    search: SearchParam = "",
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    rows, total = await repo.list_organizations(
        search=search, limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=[
            AdminOrgOut(
                id=org.id,
                name=org.name,
                slug=org.slug,
                created_at=org.created_at,
                suspended_at=org.suspended_at,
                member_count=member_count,
                owner_email=owner_email,
                owner_name=owner_name,
            )
            for org, member_count, owner_email, owner_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/customers", response_model=Page[AdminCustomerUsageOut])
async def list_customers(
    _: CurrentSuperuser,
    repo: Repo,
    search: SearchParam = "",
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
    sort: Annotated[str, Query(pattern=r"^(joined|credits)$")] = "joined",
):
    """Founder view: who signed up and how many credits they spent."""
    rows, total = await repo.list_customer_usage(
        search=search, sort=sort, limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=[AdminCustomerUsageOut.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/organizations/{org_id}/suspend", response_model=AdminOrgSuspensionOut)
async def suspend_organization(
    org_id: uuid.UUID,
    superuser: CurrentSuperuser,
    use_case: Annotated[uc.SetOrgSuspended, Depends(get_set_org_suspended)],
):
    org = await use_case.execute(superuser, org_id, suspended=True)
    return AdminOrgSuspensionOut(id=org.id, suspended_at=org.suspended_at)


@router.post("/organizations/{org_id}/unsuspend", response_model=AdminOrgSuspensionOut)
async def unsuspend_organization(
    org_id: uuid.UUID,
    superuser: CurrentSuperuser,
    use_case: Annotated[uc.SetOrgSuspended, Depends(get_set_org_suspended)],
):
    org = await use_case.execute(superuser, org_id, suspended=False)
    return AdminOrgSuspensionOut(id=org.id, suspended_at=org.suspended_at)


@router.post("/organizations/merge", response_model=MergeOrgsOut)
async def merge_organizations(
    payload: MergeOrgsRequest,
    superuser: CurrentSuperuser,
    use_case: Annotated[uc.MergeOrganizations, Depends(get_merge_organizations)],
):
    members_moved = await use_case.execute(superuser, payload.target_id, payload.source_ids)
    return MergeOrgsOut(
        target_id=payload.target_id,
        merged_count=len(payload.source_ids),
        members_moved=members_moved,
    )


@router.get("/organizations/{org_id}/members", response_model=list[AdminOrgMemberOut])
async def list_organization_members(
    org_id: uuid.UUID,
    _: CurrentSuperuser,
    repo: Repo,
    org_queries: OrgQueriesDep,
):
    if await repo.get_organization(org_id) is None:
        raise AdminOrgNotFound("Organization not found.")
    rows = await org_queries.list_members(org_id)
    return [
        AdminOrgMemberOut(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=membership.role,
            is_active=user.is_active,
            joined_at=membership.created_at,
        )
        for membership, user in rows
    ]


# -- users ----------------------------------------------------------------------


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    _: CurrentSuperuser,
    repo: Repo,
    search: SearchParam = "",
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    rows, total = await repo.list_users(
        search=search, limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=[_user_out(user, org_count) for user, org_count in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
async def deactivate_user(
    user_id: uuid.UUID,
    superuser: CurrentSuperuser,
    repo: Repo,
    use_case: Annotated[uc.SetUserActive, Depends(get_set_user_active)],
):
    user = await use_case.execute(superuser, user_id, active=False)
    return _user_out(user, await repo.count_user_organizations(user.id))


@router.post("/users/{user_id}/reactivate", response_model=AdminUserOut)
async def reactivate_user(
    user_id: uuid.UUID,
    superuser: CurrentSuperuser,
    repo: Repo,
    use_case: Annotated[uc.SetUserActive, Depends(get_set_user_active)],
):
    user = await use_case.execute(superuser, user_id, active=True)
    return _user_out(user, await repo.count_user_organizations(user.id))


@router.post("/users/{user_id}/signout-everywhere", response_model=AdminUserOut)
async def signout_user_everywhere(
    user_id: uuid.UUID,
    superuser: CurrentSuperuser,
    repo: Repo,
    use_case: Annotated[uc.SignOutUserEverywhere, Depends(get_signout_user_everywhere)],
):
    user = await use_case.execute(superuser, user_id)
    return _user_out(user, await repo.count_user_organizations(user.id))


@router.post("/users/{user_id}/impersonate", response_model=ImpersonationOut)
async def impersonate_user(
    user_id: uuid.UUID,
    superuser: CurrentSuperuser,
    use_case: Annotated[uc.ImpersonateUser, Depends(get_impersonate_user)],
):
    """Mint a short-lived access token for the target user (no refresh token —
    the impersonated session simply expires). Audit-logged."""
    token, user = await use_case.execute(superuser, user_id)
    return ImpersonationOut(access_token=token, user_id=user.id, email=user.email, name=user.name)


# -- credits ---------------------------------------------------------------------


@router.get("/credits", response_model=Page[AdminWalletOut])
async def list_credit_wallets(
    _: CurrentSuperuser,
    repo: Repo,
    search: SearchParam = "",
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    rows, total = await repo.list_wallets(
        search=search, limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=[
            AdminWalletOut(
                organization_id=wallet.organization_id,
                organization_name=org_name,
                balance=wallet.balance,
                allowance_period=wallet.allowance_period,
                pending_holds=holds,
                updated_at=wallet.updated_at,
            )
            for wallet, org_name, holds in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/organizations/{org_id}/credits/adjust", response_model=AdminWalletOut)
async def adjust_org_credits(
    org_id: uuid.UUID,
    payload: CreditAdjustRequest,
    superuser: CurrentSuperuser,
    repo: Repo,
    use_case: Annotated[uc.AdjustOrgCredits, Depends(get_adjust_org_credits)],
):
    wallet = await use_case.execute(
        superuser, org_id, amount=payload.amount, description=payload.description
    )
    org = await repo.get_organization(org_id)
    return AdminWalletOut(
        organization_id=wallet.organization_id,
        organization_name=org.name if org else "",
        balance=wallet.balance,
        allowance_period=wallet.allowance_period,
        pending_holds=0,  # not recomputed here; the list view refreshes it
        updated_at=wallet.updated_at,
    )


# -- generations -----------------------------------------------------------------


@router.get("/generations", response_model=Page[AdminGenerationOut])
async def list_generations(
    _: CurrentSuperuser,
    repo: Repo,
    status_filter: Annotated[GenerationStatus | None, Query(alias="status")] = None,
    kind: CreditAction | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    rows, total = await repo.list_generations(
        status=status_filter, kind=kind, limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=[
            AdminGenerationOut(
                id=gen.id,
                organization_id=gen.organization_id,
                organization_name=org_name,
                user_id=gen.user_id,
                kind=gen.kind,
                model=gen.model,
                status=gen.status,
                prompt=gen.prompt,
                error=gen.error,
                credits_cost=gen.credits_cost,
                created_at=gen.created_at,
                completed_at=gen.completed_at,
            )
            for gen, org_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# -- invitations -----------------------------------------------------------------


@router.get("/invitations", response_model=Page[AdminInvitationOut])
async def list_invitations(
    _: CurrentSuperuser,
    repo: Repo,
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    rows, total = await repo.list_pending_invitations(
        limit=page_size, offset=(page - 1) * page_size
    )
    return Page(
        items=[
            AdminInvitationOut(
                id=inv.id,
                organization_id=inv.organization_id,
                organization_name=org_name,
                email=inv.email,
                role=inv.role,
                invited_by_email=inviter_email,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            )
            for inv, org_name, inviter_email in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    superuser: CurrentSuperuser,
    use_case: Annotated[uc.RevokeInvitationAdmin, Depends(get_revoke_invitation)],
):
    await use_case.execute(superuser, invitation_id)


# -- audit log -------------------------------------------------------------------


@router.get("/audit-log", response_model=Page[AdminAuditOut])
async def list_audit_log(
    _: CurrentSuperuser,
    repo: Repo,
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    rows, total = await repo.list_audit_log(limit=page_size, offset=(page - 1) * page_size)
    return Page(
        items=[
            AdminAuditOut(
                id=entry.id,
                actor_email=actor.email if actor else None,
                actor_name=actor.name if actor else None,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                meta=entry.meta,
                created_at=entry.created_at,
            )
            for entry, actor in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# -- error lookup (support loop) ---------------------------------------------------


@router.get("/errors/{error_id}")
async def error_lookup(error_id: str, _: CurrentSuperuser) -> dict:
    """Resolve a user-reported error reference to its full request context.

    Users report `code · ref` from any error surface ("Copy details"); this
    returns the structured record captured at the moment of failure — route,
    status, client, and (for 500s) the traceback. Records live in Redis for
    ERROR_CONTEXT_RETENTION_DAYS days (shared/policy.toml).
    """
    context = await lookup_error_context(error_id)
    if context is None:
        raise AdminErrorRecordNotFound(
            f"No error record for that reference (expired after "
            f"{ERROR_CONTEXT_RETENTION_DAYS} days, or never existed)."
        )
    return context
