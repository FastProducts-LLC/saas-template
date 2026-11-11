"""Pluggable email service: transactional sends + marketing-list sync.

The active provider is chosen by ``EMAIL_PROVIDER`` ("smtp" for Mailpit in
development, "resend" in production; add SendGrid/SES by implementing
`EmailProvider` and registering it in `_build_provider`).

Transactional sends and marketing-list sync are dispatched to Celery tasks
(``send_email_task`` / ``marketing_sync_task``) so they don't block the
request. The tasks retry with exponential backoff on transient provider
errors.

GDPR: only call `subscribe_to_marketing_list` for users who explicitly opted
in (``User.marketing_opt_in`` is True) — never add contacts by default.
"""

import logging
import unicodedata
from functools import lru_cache

from app.core.config import settings
from app.core.email.base import EmailProvider

logger = logging.getLogger(__name__)


def _build_provider() -> EmailProvider:
    if settings.email_provider == "resend":
        from app.core.email.resend_provider import ResendProvider

        return ResendProvider()
    from app.core.email.smtp_provider import SMTPProvider

    return SMTPProvider()


@lru_cache(maxsize=1)
def get_provider() -> EmailProvider:
    return _build_provider()


def clean_subject(subject: str) -> str:
    """Collapse control characters and line breaks to single spaces.

    Subjects routinely embed user-chosen text (org names, first names). A
    CR/LF there cannot inject headers — the stdlib refuses to build the
    message — but that refusal happens in the worker, where sends are
    best-effort: the email just never arrives. Every send goes through here,
    so no stored value can break delivery."""
    cleaned = "".join(
        " " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") else ch for ch in subject
    )
    return " ".join(cleaned.split())


async def send_email(
    to: str,
    subject: str,
    *,
    text: str | None = None,
    html: str | None = None,
    tags: dict[str, str] | None = None,
) -> None:
    """Dispatch a transactional email to the Celery worker queue."""
    from app.core.email.tasks import send_email_task

    subject = clean_subject(subject)
    try:
        send_email_task.delay(to=to, subject=subject, text=text, html=html, tags=tags)
    except Exception:
        logger.exception("Failed to enqueue email to %s (subject=%r)", to, subject)


def _enqueue_marketing_sync(
    action: str, email: str, first_name: str = "", last_name: str = ""
) -> None:
    from app.core.email.tasks import marketing_sync_task

    try:
        marketing_sync_task.delay(
            action=action, email=email, first_name=first_name, last_name=last_name
        )
    except Exception:
        logger.exception("Failed to enqueue marketing %s for %s", action, email)


async def subscribe_to_marketing_list(email: str, first_name: str, last_name: str) -> None:
    """Add an explicitly opted-in contact to the marketing list."""
    _enqueue_marketing_sync("subscribe", email, first_name, last_name)


async def unsubscribe_from_marketing_list(email: str) -> None:
    """Stop broadcasts for a contact (keeps the record for re-opt-in)."""
    _enqueue_marketing_sync("unsubscribe", email)


async def delete_marketing_contact(email: str) -> None:
    """Remove a contact entirely (account deletion / GDPR erasure)."""
    _enqueue_marketing_sync("delete", email)
