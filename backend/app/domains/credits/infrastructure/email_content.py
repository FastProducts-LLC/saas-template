"""Credits transactional email content. Each builder returns (subject, text, html).

Rendering is infrastructure — copy changes never touch use-case logic.
"""

from app.core.config import settings
from app.core.email.layout import render_email


def low_balance_email(balance: int, allowance: int) -> tuple[str, str, str]:
    """Heads-up that the organization's credit balance is running low."""
    subject = f"Your {settings.app_name} credits are running low"
    credits_url = f"{settings.frontend_url}/credits"
    text = (
        "Your organization is running low on credits.\n\n"
        f"You have {balance:,} credits left out of your {allowance:,} monthly "
        f"allowance.\n\n"
        f"Top up or review your balance and history: {credits_url}"
    )
    html = render_email(
        heading="Your organization is running low on credits",
        body_html=(
            f"<p>You have <strong>{balance:,} credits</strong> left out of your "
            f"{allowance:,} monthly allowance.</p>"
            f"<p>Top up now to avoid interruptions to your metered actions.</p>"
        ),
        cta_label="View credits",
        cta_url=credits_url,
        footer_note=("We send this once per billing period so you have time to top up."),
    )
    return subject, text, html
