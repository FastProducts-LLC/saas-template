"""Email provider webhook handling: marketing-preferences sync, suppression, event log.

Three responsibilities, all driven by Resend (Svix-delivered) events:

- Marketing preferences stay in sync bidirectionally. A user can leave the
  marketing list in the app (auth's `SetMarketingOptIn`) or via the
  unsubscribe link in a broadcast; the second path arrives here as
  `contact.updated` with `unsubscribed=true` (Resend has no dedicated
  unsubscribe event) and flips `marketing_opt_in` off so the app never
  re-subscribes them. Only the opt-OUT direction is synced —
  `unsubscribed=false` rides along on every routine contact update and must
  never re-opt-in anyone.
- Dead or hostile addresses get suppressed. A hard bounce (`email.bounced`)
  means the address doesn't exist; a spam complaint (`email.complained`)
  means the user never wants to hear from us — that one also revokes
  marketing opt-in. Both set `User.email_suppressed`, which gates every
  transactional send.
- Every `email.*` event is persisted (deduped by Svix message id) so we own
  our deliverability and engagement data.
"""

import logging
from datetime import datetime

from app.domains.emails.application.ports import (
    EmailEventRepository,
    MarketingPreferencesRepository,
)
from app.domains.emails.domain import EmailEvent

logger = logging.getLogger(__name__)


def _recipient(data: dict) -> str:
    """Resend payloads carry the address as `to: [..]` on email.* events and
    as `email` / `email_address` on contact + legacy shapes."""
    to = data.get("to") or []
    return (to[0] if to else "") or data.get("email_address") or data.get("email") or ""


def _occurred_at(data: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(data.get("created_at")))
    except (ValueError, TypeError):
        return None


class ProcessResendEvent:
    def __init__(self, prefs: MarketingPreferencesRepository, events: EmailEventRepository) -> None:
        self.prefs = prefs
        self.events = events

    async def handle(self, event: dict, svix_id: str | None = None) -> None:
        event_type = event.get("type", "")
        data = event.get("data") or {}
        if event_type == "contact.unsubscribed" or (
            event_type == "contact.updated" and data.get("unsubscribed")
        ):
            email = data.get("email", "")
            if email and await self.prefs.set_marketing_opt_out(email):
                logger.info("Synced unsubscribe from Resend webhook: %s", email)
        elif event_type.startswith("email."):
            await self._record(event_type, data, svix_id)
            if event_type in ("email.bounced", "email.complained"):
                await self._suppress(event_type, data)
        else:
            logger.debug("Ignoring Resend webhook event type: %s", event_type)

    async def _record(self, event_type: str, data: dict, svix_id: str | None) -> None:
        if svix_id and await self.events.seen(svix_id):
            return  # Svix redelivered a message we already stored
        await self.events.add(
            EmailEvent(
                event=event_type,
                recipient=_recipient(data),
                subject=(data.get("subject") or "")[:255],
                email_id=data.get("email_id") or "",
                svix_id=svix_id or None,
                occurred_at=_occurred_at(data),
                payload=data,
            )
        )

    async def _suppress(self, event_type: str, data: dict) -> None:
        email = _recipient(data)
        if not email:
            return
        if event_type == "email.complained":
            # A spam complaint suppresses the address AND revokes marketing
            # opt-out in a single UPDATE.
            suppressed = await self.prefs.suppress_and_opt_out(email)
        else:
            suppressed = await self.prefs.suppress_email(email)
        logger.warning(
            "%s for %s — %s",
            event_type,
            email,
            "suppressed user" if suppressed else "no matching user",
        )
