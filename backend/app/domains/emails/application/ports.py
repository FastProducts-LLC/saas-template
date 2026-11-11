"""Emails application ports."""

from typing import Protocol

from app.domains.emails.domain import EmailEvent


class MarketingPreferencesRepository(Protocol):
    """Marketing/deliverability flags on user records. Satisfied structurally
    by auth's users-table writer (auth owns `users`); named distinctly from the
    unrelated consents slice (GDPR consent_events)."""

    async def set_marketing_opt_out(self, email: str) -> bool:
        """Flip marketing_opt_in off for the matching user. Returns True if found."""
        ...

    async def suppress_email(self, email: str) -> bool:
        """Mark the matching user's address as undeliverable (hard bounce /
        spam complaint). Returns True if found."""
        ...

    async def suppress_and_opt_out(self, email: str) -> bool:
        """Suppress the address AND revoke marketing opt-in in a single
        UPDATE (spam-complaint path). Returns True if found."""
        ...


class EmailEventRepository(Protocol):
    async def seen(self, svix_id: str) -> bool:
        """True if an event with this Svix delivery id is already stored."""
        ...

    async def add(self, event: EmailEvent) -> None: ...
