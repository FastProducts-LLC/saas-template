"""Invitation email delivery — implements the InvitationNotifier port.

Owns the accept-URL construction and the message copy, so the use case
never sees settings or email plumbing.
"""

from html import escape

from app.core.config import settings
from app.core.email import send_email
from app.core.email.layout import render_email
from app.domains.auth.domain import User
from app.domains.organizations.domain import Invitation, Organization


class EmailInvitationNotifier:
    async def send_invitation(
        self, invitation: Invitation, org: Organization, inviter: User, raw_token: str
    ) -> None:
        accept_url = f"{settings.frontend_url}/invitations/accept?token={raw_token}"
        await send_email(
            invitation.email,
            f"You've been invited to {org.name}",
            text=(
                f"{inviter.name} invited you to join {org.name} on {settings.app_name}.\n\n"
                f"Accept the invitation: {accept_url}\n\n"
                f"This link expires in {settings.invitation_ttl_days} days."
            ),
            html=render_email(
                heading=f"Join {org.name}",
                body_html=(
                    f"<p>{escape(inviter.name)} invited you to join "
                    f"<strong>{escape(org.name)}</strong> on {escape(settings.app_name)}.</p>"
                ),
                cta_label="Accept invitation",
                cta_url=accept_url,
                footer_note=f"This link expires in {settings.invitation_ttl_days} days.",
            ),
            tags={"type": "invitation"},
        )
