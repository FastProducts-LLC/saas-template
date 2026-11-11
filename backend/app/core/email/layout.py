"""Shared HTML email layout.

Inline styles + table layout for broad email-client compatibility. Feature
slices compose messages with `render_email`
(see `app/domains/auth/infrastructure/email_content.py`).
"""

from html import escape

from app.core.brand import (
    EMAIL_BACKGROUND,
    EMAIL_FAINT,
    EMAIL_MUTED,
    EMAIL_ON_ACCENT,
    EMAIL_RULE,
    EMAIL_SURFACE,
    EMAIL_TEXT,
    THEME_ACCENT,
    THEME_INK,
)
from app.core.config import settings

# Brand accent from shared/brand.toml — emails follow the same source of
# truth as the frontend theme instead of hardcoding their own palette.
_BUTTON_STYLE = (
    f"display:inline-block;background:{THEME_ACCENT};color:{EMAIL_ON_ACCENT};text-decoration:none;"
    "padding:12px 24px;border-radius:6px;font-size:14px;font-weight:600;"
)


def render_email(
    *,
    heading: str,
    body_html: str,
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_note: str | None = None,
) -> str:
    """Wrap content in the branded base layout. `body_html` is trusted markup —
    escape any user-supplied values before interpolating into it."""
    app_name = escape(settings.email_from_name or settings.app_name)
    cta = ""
    if cta_label and cta_url:
        cta = (
            f'<p style="margin:28px 0;">'
            f'<a href="{escape(cta_url)}" style="{_BUTTON_STYLE}">{escape(cta_label)}</a></p>'
        )
    note = ""
    if footer_note:
        note = f'<p style="color:{EMAIL_MUTED};font-size:13px;">{escape(footer_note)}</p>'
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;\
margin:0;padding:24px 0;background:{EMAIL_BACKGROUND};">
  <table width="100%" cellpadding="0" cellspacing="0" \
style="max-width:600px;margin:0 auto;background:{EMAIL_SURFACE};border-radius:8px;padding:40px;">
    <tr><td>
      <h1 style="margin:0 0 16px;font-size:20px;color:{THEME_INK};">{escape(heading)}</h1>
      <div style="color:{EMAIL_TEXT};font-size:15px;line-height:1.6;">{body_html}</div>
      {cta}
      {note}
    </td></tr>
    <tr><td style="padding-top:32px;border-top:1px solid {EMAIL_RULE};color:{EMAIL_FAINT};font-size:12px;">
      <p style="margin:8px 0 0;">&copy; {app_name}. All rights reserved.</p>
    </td></tr>
  </table>
</body>
</html>"""
