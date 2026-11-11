"""Consent endpoints — signed-in users only.

Anonymous visitors keep a client-side record; the frontend syncs to these
endpoints best-effort once a user is authenticated (see the consent feature's
hooks). GET returns the latest decision or null so the client can reconcile
a choice made on another device.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.domains.auth.interface.deps import CurrentUser
from app.domains.consents.application import use_cases as uc
from app.domains.consents.interface.deps import get_current_consent, get_record_consent
from app.domains.consents.interface.schemas import ConsentIn, ConsentOut

router = APIRouter(prefix="/consent", tags=["consent"])


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
async def record_consent(
    request: Request,
    body: ConsentIn,
    user: CurrentUser,
    use_case: Annotated[uc.RecordConsent, Depends(get_record_consent)],
):
    event = await use_case.execute(
        user_id=user.id,
        analytics=body.analytics,
        policy_version=body.policy_version,
        ip_address=_client_ip(request),
        # Truncate at the HTTP edge — the column is String(255).
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    )
    return ConsentOut.from_entity(event)


@router.get("", response_model=ConsentOut | None)
async def current_consent(
    user: CurrentUser,
    use_case: Annotated[uc.GetCurrentConsent, Depends(get_current_consent)],
):
    event = await use_case.execute(user_id=user.id)
    return ConsentOut.from_entity(event) if event else None
