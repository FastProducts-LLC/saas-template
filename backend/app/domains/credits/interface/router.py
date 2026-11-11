"""Credits HTTP endpoints: action costs, wallet summary, history, per-actor
usage rollups, and admin-managed per-member monthly limits."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.domains.credits.application.queries import CreditUsageQueries, current_period
from app.domains.credits.application.use_cases import (
    ClearMemberCreditLimit,
    CreditEngine,
    ListMemberCreditLimits,
    SetMemberCreditLimit,
)
from app.domains.credits.domain import ACTIONS, MONTHLY_ALLOWANCE_CREDITS, ReservationStatus
from app.domains.credits.interface.deps import (
    get_clear_member_limit,
    get_credit_engine,
    get_list_member_limits,
    get_set_member_limit,
    get_usage_queries,
)
from app.domains.credits.interface.schemas import (
    ActionCostOut,
    HistoryOut,
    MemberLimitIn,
    MemberLimitOut,
    ReservationOut,
    TransactionOut,
    UsageActionOut,
    UsageActorOut,
    UsageOut,
    WalletOut,
)
from app.domains.organizations.interface.deps import CurrentAdmin, CurrentMember

router = APIRouter(tags=["credits"])

Engine = Annotated[CreditEngine, Depends(get_credit_engine)]


@router.get("/credits/actions", response_model=list[ActionCostOut])
async def list_action_costs():
    return [
        ActionCostOut(action=spec.action, name=spec.name, cost=spec.cost)
        for spec in ACTIONS.values()
    ]


@router.get("/orgs/{org_id}/credits", response_model=WalletOut)
async def get_wallet(membership: CurrentMember, engine: Engine):
    wallet, pending = await engine.summary(membership.organization_id)
    return WalletOut(
        balance=wallet.balance,
        reserved=sum(r.amount for r in pending),
        monthly_allowance=MONTHLY_ALLOWANCE_CREDITS,
        allowance_period=wallet.allowance_period,
        pending_holds=[
            ReservationOut(
                id=r.id,
                action=r.action,
                amount=r.amount,
                status=r.status,
                reference=r.reference,
                expires_at=r.expires_at,
                created_at=r.created_at,
            )
            for r in pending
        ],
    )


@router.get("/orgs/{org_id}/credits/history", response_model=HistoryOut)
async def get_history(
    membership: CurrentMember,
    engine: Engine,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows, total = await engine.history(membership.organization_id, limit=limit, offset=offset)
    items = [
        TransactionOut(
            id=tx.id,
            type=tx.type,
            action=tx.action,
            amount=tx.amount,
            balance_after=tx.balance_after,
            description=tx.description,
            user_email=user_email,
            api_key_name=api_key_name,
            reservation_status=ReservationStatus(res_status) if res_status else None,
            created_at=tx.created_at,
        )
        for tx, user_email, api_key_name, res_status in rows
    ]
    return HistoryOut(items=items, total=total)


@router.get("/orgs/{org_id}/credits/usage", response_model=UsageOut)
async def get_usage(
    membership: CurrentMember,
    usage: Annotated[CreditUsageQueries, Depends(get_usage_queries)],
    period: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Credits spent this period, grouped by actor (member or API key).

    Member-visible: /credits/history already exposes per-user emails and
    amounts to every member, and members should see their own limit progress.
    """
    resolved = period or current_period()
    actors, total_actors, total_credits = await usage.usage_for_period(
        membership.organization_id, resolved, limit=limit, offset=offset
    )
    return UsageOut(
        period=resolved,
        items=[
            UsageActorOut(
                user_id=a.user_id,
                user_email=a.user_email,
                user_name=a.user_name,
                api_key_id=a.api_key_id,
                api_key_name=a.api_key_name,
                credits=a.credits,
                count=a.count,
                limit=a.limit,
                actions=[
                    UsageActionOut(action=x.action, count=x.count, credits=x.credits)
                    for x in a.actions
                ],
            )
            for a in actors
        ],
        total_actors=total_actors,
        total_credits=total_credits,
    )


# -- per-member monthly credit limits (admin-only; API keys can't reach these
# by construction — they are capped at MEMBER) --------------------------------


@router.get("/orgs/{org_id}/credits/member-limits", response_model=list[MemberLimitOut])
async def list_member_limits(
    admin: CurrentAdmin,
    use_case: Annotated[ListMemberCreditLimits, Depends(get_list_member_limits)],
):
    rows = await use_case.execute(admin.organization_id)
    return [
        MemberLimitOut(
            user_id=limit.user_id,
            email=email,
            monthly_limit=limit.monthly_limit,
            used_this_period=used,
            updated_at=limit.updated_at,
        )
        for limit, email, used in rows
    ]


@router.put("/orgs/{org_id}/credits/member-limits/{user_id}", response_model=MemberLimitOut)
async def set_member_limit(
    user_id: uuid.UUID,
    body: MemberLimitIn,
    admin: CurrentAdmin,
    use_case: Annotated[SetMemberCreditLimit, Depends(get_set_member_limit)],
    listing: Annotated[ListMemberCreditLimits, Depends(get_list_member_limits)],
):
    limit = await use_case.execute(admin.organization_id, user_id, body.monthly_limit)
    rows = await listing.execute(admin.organization_id)
    email, used = next(
        ((e, u) for lim, e, u in rows if lim.user_id == user_id),
        (None, 0),
    )
    return MemberLimitOut(
        user_id=limit.user_id,
        email=email,
        monthly_limit=limit.monthly_limit,
        used_this_period=used,
        updated_at=limit.updated_at,
    )


@router.delete("/orgs/{org_id}/credits/member-limits/{user_id}", status_code=204)
async def clear_member_limit(
    user_id: uuid.UUID,
    admin: CurrentAdmin,
    use_case: Annotated[ClearMemberCreditLimit, Depends(get_clear_member_limit)],
):
    await use_case.execute(admin.organization_id, user_id)
    return Response(status_code=204)
