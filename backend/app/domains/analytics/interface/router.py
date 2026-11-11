"""First-party analytics ingest — POST /api/events.

Contract (deliberately unlike the rest of the API):
- 401 without a valid session — anonymous activity is never recorded.
- 204 for EVERY authenticated request, whether the event was stored or
  dropped (unknown name, bad shape, opted out, rate-limited). No validation
  oracle, and the client is fire-and-forget anyway. Drops log at debug.
- The user is the session's user. A `user_id` in the body is ignored.

The body is parsed by hand rather than through a Pydantic model so a
malformed payload yields 204 instead of the 422 envelope.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.domains.analytics.application import use_cases as uc
from app.domains.analytics.domain.policy import MAX_BODY_BYTES
from app.domains.analytics.interface.deps import get_record_client_event
from app.domains.auth.interface.deps import CurrentUser

router = APIRouter(tags=["analytics"])

_NO_CONTENT = status.HTTP_204_NO_CONTENT


async def _read_payload(request: Request) -> dict | None:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return None
    try:
        payload = json.loads(body)
    except ValueError:  # includes UnicodeDecodeError
        return None
    return payload if isinstance(payload, dict) else None


@router.post(
    "/events",
    status_code=_NO_CONTENT,
    summary="Record a product-analytics event for the signed-in user",
    description=(
        'Body: `{"event": "<client event name>", "properties": {...}}`. Only names from '
        "the `[client.*]` tables of shared/events.toml are stored; properties are scalar "
        "identifiers/enums/numbers. Always answers 204 when authenticated."
    ),
)
async def ingest_event(
    request: Request,
    user: CurrentUser,
    use_case: Annotated[uc.RecordClientEvent, Depends(get_record_client_event)],
) -> Response:
    payload = await _read_payload(request)
    if payload is not None:
        await use_case.execute(
            user_id=user.id,
            opted_out=user.analytics_opt_out,
            event=payload.get("event"),
            properties=payload.get("properties"),
        )
    return Response(status_code=_NO_CONTENT)
