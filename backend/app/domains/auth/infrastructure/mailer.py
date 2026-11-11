"""Auth mailer + marketing-list adapters.

`TransactionalAuthMailer` owns the full edge concern: mint the action token,
build the frontend link, render the copy, hand off to the provider-agnostic
email service. Use cases just say *what* to send.
"""

import logging
from datetime import timedelta

from app.core import security
from app.core.config import settings
from app.core.email import (
    send_email,
    subscribe_to_marketing_list,
    unsubscribe_from_marketing_list,
)
from app.domains.auth.application.use_cases import PURPOSE_PASSWORD_RESET, PURPOSE_VERIFY_EMAIL
from app.domains.auth.domain import User
from app.domains.auth.infrastructure import email_content

logger = logging.getLogger(__name__)


def _sendable(user: User) -> bool:
    """Suppressed addresses (hard bounce / spam complaint) get no email at all
    — sending anyway burns sender reputation and Resend would reject it."""
    if user.email_suppressed:
        logger.info("Skipping email to suppressed address %s", user.email)
        return False
    return True


def _link(path: str, token: str) -> str:
    """Email link carrying an action token in the URL *fragment*. Fragments
    never leave the browser: they aren't sent to servers, so the token stays
    out of proxy/CDN/access logs and Referer headers (a query string lands in
    all of them). The SPA reads it and scrubs it from the address bar."""
    return f"{settings.frontend_url}{path}#token={token}"


class TransactionalAuthMailer:
    async def send_welcome_with_verification(self, user: User) -> None:
        if not _sendable(user):
            return
        subject, text, html = email_content.welcome_email(user, self._verification_url(user))
        await send_email(user.email, subject, text=text, html=html, tags={"type": "welcome"})

    async def send_verification(self, user: User) -> None:
        if not _sendable(user):
            return
        subject, text, html = email_content.verification_email(user, self._verification_url(user))
        await send_email(user.email, subject, text=text, html=html, tags={"type": "verification"})

    async def send_account_exists_notice(self, user: User) -> None:
        if not _sendable(user):
            return
        subject, text, html = email_content.account_exists_email(
            user,
            f"{settings.frontend_url}/login",
            f"{settings.frontend_url}/forgot-password",
        )
        await send_email(user.email, subject, text=text, html=html, tags={"type": "account_exists"})

    async def send_password_reset(self, user: User, single_use_claims: dict) -> None:
        if not _sendable(user):
            return
        token = security.create_action_token(
            str(user.id),
            PURPOSE_PASSWORD_RESET,
            timedelta(minutes=settings.password_reset_ttl_minutes),
            single_use_claims,
        )
        reset_url = _link("/reset-password", token)
        subject, text, html = email_content.password_reset_email(user, reset_url)
        await send_email(user.email, subject, text=text, html=html, tags={"type": "password_reset"})

    async def send_password_changed(self, user: User) -> None:
        if not _sendable(user):
            return
        subject, text, html = email_content.password_changed_email(
            user, f"{settings.frontend_url}/forgot-password"
        )
        await send_email(
            user.email, subject, text=text, html=html, tags={"type": "password_changed"}
        )

    @staticmethod
    def _verification_url(user: User) -> str:
        token = security.create_action_token(
            str(user.id),
            PURPOSE_VERIFY_EMAIL,
            timedelta(hours=settings.email_verification_ttl_hours),
        )
        return _link("/verify-email", token)


class ProviderMarketingList:
    """MarketingList port → the pluggable email provider (SMTP no-op / Resend)."""

    async def subscribe(self, email: str, first_name: str, last_name: str) -> None:
        await subscribe_to_marketing_list(email, first_name, last_name)

    async def unsubscribe(self, email: str) -> None:
        await unsubscribe_from_marketing_list(email)
