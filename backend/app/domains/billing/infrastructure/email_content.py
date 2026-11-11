"""Billing transactional email content. Each builder returns (subject, text, html).

Rendering is infrastructure — copy changes never touch use-case logic.
"""

from html import escape

from app.core.config import settings
from app.core.email.layout import render_email


def credit_pack_receipt_email(pack_name: str, credits: int) -> tuple[str, str, str]:
    """Confirmation that a one-time credit pack was purchased and applied."""
    subject = f"{credits:,} credits added to your {settings.app_name} organization"
    credits_url = f"{settings.frontend_url}/credits"
    text = (
        f"Thanks for your purchase!\n\n"
        f"Your {pack_name} ({credits:,} credits) has been applied to your "
        f"organization's balance.\n\n"
        f"See your balance and history: {credits_url}"
    )
    html = render_email(
        heading="Credits added",
        body_html=(
            f"<p>Thanks for your purchase! Your <strong>{escape(pack_name)}</strong> "
            f"({credits:,} credits) has been applied to your organization's balance.</p>"
        ),
        cta_label="View credits",
        cta_url=credits_url,
        footer_note="Your Stripe receipt arrives separately from stripe.com.",
    )
    return subject, text, html
