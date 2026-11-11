"""Emails background composition root (no request context)."""

from app.core.database import SessionLocal
from app.domains.auth.interface.deps import build_marketing_preferences_repository


async def is_address_suppressed(email: str) -> bool:
    """Suppression lookup for the send chokepoint. Auth owns `users`; its
    marketing-preferences repository answers the question."""
    async with SessionLocal() as session:
        return await build_marketing_preferences_repository(session).is_email_suppressed(email)
