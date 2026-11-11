"""Public + admin HTTP endpoints for data-subject privacy requests.

Public intake is unauthenticated (rate-limited). Fulfillment is superuser-only:
mark fulfilled with a note and optionally record an upstream-processor forward.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.core.policy import ADMIN_PAGE_SIZE, RATE_LIMIT_PRIVACY_REQUEST_SUBMIT
from app.core.ratelimit import limiter
from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.privacy_requests.application import use_cases as uc
from app.domains.privacy_requests.domain import PrivacyRequestNotFound
from app.domains.privacy_requests.domain.entities import PrivacyRequestStatus, PrivacyRequestType
from app.domains.privacy_requests.infrastructure.repositories import (
    SqlAlchemyPrivacyRequestRepository,
)
from app.domains.privacy_requests.interface.deps import (
    get_close_privacy_request,
    get_forward_privacy_request,
    get_fulfill_privacy_request,
    get_privacy_request_repo,
    get_reject_privacy_request,
    get_submit_privacy_request,
    get_verify_privacy_request,
)
from app.domains.privacy_requests.interface.schemas import (
    CloseIn,
    ForwardIn,
    FulfillIn,
    PrivacyRequestOut,
    PrivacyRequestPage,
    PrivacyRequestSubmitIn,
    PrivacyRequestSubmitOut,
    RejectIn,
)

# Public intake (no auth)
public_router = APIRouter(tags=["privacy"])

# Superuser ops queue
admin_router = APIRouter(prefix="/admin/privacy-requests", tags=["admin-privacy"])

Repo = Annotated[SqlAlchemyPrivacyRequestRepository, Depends(get_privacy_request_repo)]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@public_router.post(
    "/privacy/requests",
    response_model=PrivacyRequestSubmitOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_PRIVACY_REQUEST_SUBMIT)
async def submit_privacy_request(
    request: Request,
    response: Response,
    body: PrivacyRequestSubmitIn,
    use_case: Annotated[uc.SubmitPrivacyRequest, Depends(get_submit_privacy_request)],
):
    req = await use_case.execute(
        request_type=PrivacyRequestType(body.request_type),
        requester_email=str(body.requester_email),
        requester_name=body.requester_name,
        subject_email=str(body.subject_email) if body.subject_email else None,
        subject_phone=body.subject_phone,
        subject_consumer_key=body.subject_consumer_key,
        subject_first_name=body.subject_first_name,
        subject_last_name=body.subject_last_name,
        notes=body.notes,
        ip_address=_client_ip(request),
    )
    return PrivacyRequestSubmitOut(
        id=req.id,
        request_type=req.request_type.value,  # type: ignore[arg-type]
        status=req.status.value,  # type: ignore[arg-type]
        deadline_at=req.deadline_at,
    )


@admin_router.get("", response_model=PrivacyRequestPage)
async def list_privacy_requests(
    _: CurrentSuperuser,
    repo: Repo,
    status_filter: Annotated[str | None, Query(alias="status", max_length=16)] = None,
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    parsed: PrivacyRequestStatus | None = None
    if status_filter:
        try:
            parsed = PrivacyRequestStatus(status_filter)
        except ValueError:
            parsed = None
    items, total = await repo.list_requests(
        status=parsed, limit=page_size, offset=(page - 1) * page_size
    )
    return PrivacyRequestPage(
        items=[PrivacyRequestOut.from_entity(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.get("/{request_id}", response_model=PrivacyRequestOut)
async def get_privacy_request(
    request_id: uuid.UUID,
    _: CurrentSuperuser,
    repo: Repo,
):
    req = await repo.get(request_id)
    if req is None:
        raise PrivacyRequestNotFound("Privacy request not found.")
    return PrivacyRequestOut.from_entity(req)


@admin_router.post("/{request_id}/verify", response_model=PrivacyRequestOut)
async def verify_privacy_request(
    request_id: uuid.UUID,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.VerifyPrivacyRequest, Depends(get_verify_privacy_request)],
):
    req = await use_case.execute(request_id, actor_user_id=admin.id)
    return PrivacyRequestOut.from_entity(req)


@admin_router.post("/{request_id}/forward", response_model=PrivacyRequestOut)
async def forward_privacy_request(
    request_id: uuid.UUID,
    body: ForwardIn,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.ForwardPrivacyRequest, Depends(get_forward_privacy_request)],
):
    req = await use_case.execute(
        request_id,
        actor_user_id=admin.id,
        provider_reference=body.provider_reference,
        notes=body.notes,
    )
    return PrivacyRequestOut.from_entity(req)


@admin_router.post("/{request_id}/fulfill", response_model=PrivacyRequestOut)
async def fulfill_privacy_request(
    request_id: uuid.UUID,
    body: FulfillIn,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.FulfillPrivacyRequest, Depends(get_fulfill_privacy_request)],
):
    req = await use_case.execute(
        request_id,
        actor_user_id=admin.id,
        provider_reference=body.provider_reference,
        notes=body.notes,
        also_forward=body.also_forward,
    )
    return PrivacyRequestOut.from_entity(req)


@admin_router.post("/{request_id}/close", response_model=PrivacyRequestOut)
async def close_privacy_request(
    request_id: uuid.UUID,
    body: CloseIn,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.ClosePrivacyRequest, Depends(get_close_privacy_request)],
):
    req = await use_case.execute(request_id, actor_user_id=admin.id, notes=body.notes)
    return PrivacyRequestOut.from_entity(req)


@admin_router.post("/{request_id}/reject", response_model=PrivacyRequestOut)
async def reject_privacy_request(
    request_id: uuid.UUID,
    body: RejectIn,
    admin: CurrentSuperuser,
    use_case: Annotated[uc.RejectPrivacyRequest, Depends(get_reject_privacy_request)],
):
    req = await use_case.execute(request_id, actor_user_id=admin.id, reason=body.reason)
    return PrivacyRequestOut.from_entity(req)
