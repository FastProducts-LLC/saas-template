"""Resend provider: transactional via the Emails API, marketing via Contacts/Segments.

Uses the SDK's native async calls (the `resend[async]` extra installs httpx,
which the SDK auto-detects).

Setup (see https://resend.com):
  1. Verify your sending domain (SPF + DKIM + DMARC records).
  2. Create an API key scoped to sending + contact access → RESEND_API_KEY.
  3. Create a "Marketing" segment in the dashboard → RESEND_SEGMENT_MARKETING.
  4. Add a webhook pointing at /api/webhooks/resend, subscribed to all
     `email.*` events plus `contact.updated` (unsubscribes arrive as
     `contact.updated` with `unsubscribed: true` — there is no
     `contact.unsubscribed` event) → RESEND_WEBHOOK_SECRET. Required in
     production: it drives opt-out sync and bounce/complaint suppression.
"""

import resend

from app.core.config import settings
from app.core.email.base import EmailProvider


class ResendProvider(EmailProvider):
    def __init__(self) -> None:
        resend.api_key = settings.resend_api_key

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        text: str | None = None,
        html: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        params: resend.Emails.SendParams = {
            "from": settings.email_sender,
            "to": [to],
            "subject": subject,
        }
        if html:
            params["html"] = html
        if text:
            params["text"] = text
        if settings.support_email:
            params["reply_to"] = [settings.support_email]
        if tags:
            params["tags"] = [{"name": k, "value": v} for k, v in tags.items()]
        await resend.Emails.send_async(params)

    async def subscribe_to_marketing(self, *, email: str, first_name: str, last_name: str) -> None:
        # Contacts are global and deduplicated by email — create is a no-op if
        # the contact exists, so create → mark subscribed → enroll in segment.
        await resend.Contacts.create_async(
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "unsubscribed": False,
            }
        )
        await resend.Contacts.update_async({"email": email, "unsubscribed": False})
        if settings.resend_segment_marketing:
            await resend.Contacts.Segments.add_async(
                {"email": email, "segment_id": settings.resend_segment_marketing}
            )

    async def unsubscribe_from_marketing(self, *, email: str) -> None:
        # Keep the contact (history, re-opt-in) but stop all broadcasts.
        await resend.Contacts.update_async({"email": email, "unsubscribed": True})

    async def delete_contact(self, *, email: str) -> None:
        await resend.Contacts.remove_async(email=email)
