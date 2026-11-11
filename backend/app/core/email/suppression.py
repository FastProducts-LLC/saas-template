"""Suppression gate for every outbound email.

A hard bounce or spam complaint marks an address as suppressed (see
`domains/emails`). That flag must stop ALL mail to the address — welcome,
receipts, invitations, alerts — not just the mailers that remember to check
it, so the check sits at the single send chokepoint (`send_email_task`).

Core cannot import a slice, so the lookup is injected: the emails slice
registers one at worker start-up (`app/domains/emails/tasks.py`, picked up by
Celery autodiscovery). With nothing registered (SMTP-only scripts, unit
tests) no address is treated as suppressed.
"""

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

SuppressionCheck = Callable[[str], Awaitable[bool]]

_check: SuppressionCheck | None = None


def register_suppression_check(check: SuppressionCheck | None) -> None:
    """Install (or, with None, clear) the address → suppressed? lookup."""
    global _check
    _check = check


async def is_suppressed(email: str) -> bool:
    """True if mail to this address must not be sent. A failing lookup
    propagates so the send task retries rather than mailing a dead address."""
    if _check is None:
        return False
    return await _check(email)
