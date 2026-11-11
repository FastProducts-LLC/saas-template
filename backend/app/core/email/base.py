"""Email provider interface.

Implement this to plug in a new provider (SendGrid, AWS SES, Postmark, …):
add a module next to `smtp_provider.py` / `resend_provider.py` and register it
in the factory in `app/core/email/__init__.py`.

Transactional sends are required; the marketing-list methods default to
logged no-ops so transactional-only providers (e.g. plain SMTP) work as-is.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    # ── Transactional ────────────────────────────────────────────────

    @abstractmethod
    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        text: str | None = None,
        html: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Send a 1:1 transactional email (welcome, reset, invitation, …)."""

    # ── Marketing list (opted-in contacts) ───────────────────────────

    async def subscribe_to_marketing(self, *, email: str, first_name: str, last_name: str) -> None:
        """Upsert a contact onto the marketing list. Caller enforces opt-in."""
        logger.info("Marketing subscribe (no-op for %s): %s", type(self).__name__, email)

    async def unsubscribe_from_marketing(self, *, email: str) -> None:
        """Mark a contact unsubscribed (keep the record, stop broadcasts)."""
        logger.info("Marketing unsubscribe (no-op for %s): %s", type(self).__name__, email)

    async def delete_contact(self, *, email: str) -> None:
        """Remove a contact entirely (account deletion / GDPR erasure)."""
        logger.info("Contact delete (no-op for %s): %s", type(self).__name__, email)
