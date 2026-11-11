"""Billing mailer adapter — implements the PurchaseReceiptMailer port.

Best-effort like every mailer: `send_email` logs failures and never raises,
so a mail outage can't fail (or replay) a webhook grant.
"""

from app.core.email import send_email
from app.domains.billing.infrastructure import email_content


class BillingReceiptMailer:
    async def send_credit_pack_receipt(self, email: str, pack_name: str, credits: int) -> None:
        subject, text, html = email_content.credit_pack_receipt_email(pack_name, credits)
        await send_email(email, subject, text=text, html=html, tags={"type": "credit_receipt"})
