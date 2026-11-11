"""Credits mailer adapter — implements the LowBalanceNotifier port.

Best-effort like every mailer: `send_email` logs failures and never raises,
so a mail outage can't fail (or block) a credit reservation.
"""

from app.core.email import send_email
from app.domains.credits.infrastructure import email_content


class CreditsMailer:
    async def notify_low_balance(
        self, *, balance: int, allowance: int, recipient_emails: list[str]
    ) -> None:
        subject, text, html = email_content.low_balance_email(balance, allowance)
        for email in recipient_emails:
            await send_email(email, subject, text=text, html=html, tags={"type": "low_balance"})
