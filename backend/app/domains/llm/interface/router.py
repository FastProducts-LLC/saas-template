"""LLM HTTP endpoints — thin: parse request → use case → serialize."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status

from app.core.policy import RATE_LIMIT_LLM_COMPLETE
from app.core.ratelimit import limiter
from app.domains.auth.interface.deps import CurrentVerifiedUser
from app.domains.llm.application.use_cases import StartLlmCall
from app.domains.llm.domain import LlmCallNotFound
from app.domains.llm.infrastructure.repositories import SqlAlchemyLlmCallRepository
from app.domains.llm.interface.deps import get_llm_call_repository, get_start_llm_call
from app.domains.llm.interface.schemas import CompleteRequest, LlmCallOut
from app.domains.llm.worker import enqueue_llm_call
from app.domains.organizations.interface.deps import CurrentMember

router = APIRouter(tags=["llm"])

Repo = Annotated[SqlAlchemyLlmCallRepository, Depends(get_llm_call_repository)]


@router.post(
    "/orgs/{org_id}/llm/complete",
    response_model=LlmCallOut,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(RATE_LIMIT_LLM_COMPLETE)
async def complete_text(
    request: Request,
    response: Response,
    payload: CompleteRequest,
    membership: CurrentMember,
    user: CurrentVerifiedUser,
    background: BackgroundTasks,
    use_case: Annotated[StartLlmCall, Depends(get_start_llm_call)],
):
    call = await use_case.execute(
        membership.organization_id,
        user.id,
        payload.provider,
        payload.prompt,
        payload.max_tokens,
    )
    # Enqueued after the request transaction commits; the worker finalizes
    # the call and its credit hold in its own session.
    background.add_task(enqueue_llm_call, call.id)
    return LlmCallOut.from_call(call)


@router.get("/orgs/{org_id}/llm/calls", response_model=list[LlmCallOut])
async def list_llm_calls(
    membership: CurrentMember,
    repo: Repo,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items = await repo.list_for_org(membership.organization_id, limit=limit, offset=offset)
    return [LlmCallOut.from_call(c) for c in items]


@router.get("/orgs/{org_id}/llm/calls/{call_id}", response_model=LlmCallOut)
async def get_llm_call(call_id: uuid.UUID, membership: CurrentMember, repo: Repo):
    call = await repo.get_for_org(membership.organization_id, call_id)
    if call is None:
        raise LlmCallNotFound("LLM call not found.")
    return LlmCallOut.from_call(call)
