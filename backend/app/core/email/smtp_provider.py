"""Plain SMTP provider. Points at Mailpit in development.

Transactional only — marketing-list methods fall back to the logged no-ops
in `EmailProvider`, so dev signups never touch a real marketing list.
"""

from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.email.base import EmailProvider


class SMTPProvider(EmailProvider):
    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        text: str | None = None,
        html: str | None = None,
        tags: dict[str, str] | None = None,  # unused by SMTP
    ) -> None:
        msg = EmailMessage()
        msg["From"] = settings.email_sender
        msg["To"] = to
        if settings.support_email:
            msg["Reply-To"] = settings.support_email
        msg["Subject"] = subject
        msg.set_content(text or "")
        if html:
            msg.add_alternative(html, subtype="html")
        await aiosmtplib.send(msg, hostname=settings.smtp_host, port=settings.smtp_port)
