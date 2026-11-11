"""Email provider webhook endpoint — thin: verify → parse → use case.

Resend signs webhooks with Svix. Configure in the Resend dashboard
(Settings → Webhooks → https://yourdomain.com/api/webhooks/resend, events:
all `email.*` plus `contact.updated`) and set the signing secret as
RESEND_WEBHOOK_SECRET. Enable Open/Click Tracking on the domain if you want
`email.opened` / `email.clicked` events.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.domains.emails.application.use_cases import ProcessResendEvent
from app.domains.emails.infrastructure.webhooks import ResendWebhookVerifier
from app.domains.emails.interface.deps import get_process_resend_event, get_webhook_verifier

router = APIRouter(tags=["emails"])


@router.post("/webhooks/resend", include_in_schema=False)
async def resend_webhook(
    request: Request,
    use_case: Annotated[ProcessResendEvent, Depends(get_process_resend_event)],
    verifier: Annotated[ResendWebhookVerifier, Depends(get_webhook_verifier)],
):
    body = await request.body()
    if not verifier.verify(body, request.headers):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    await use_case.handle(event, svix_id=request.headers.get("svix-id"))
    return {"received": True}
