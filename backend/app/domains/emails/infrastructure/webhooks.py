"""Resend webhook-signature verification adapter (the only place the resend
SDK is touched in this slice)."""

import logging
from collections.abc import Mapping

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResendWebhookVerifier:
    """Svix HMAC verification via the Resend SDK (timestamp tolerance included)."""

    def verify(self, body: bytes, headers: Mapping[str, str]) -> bool:
        if not settings.resend_webhook_secret:
            # Unsigned webhooks are accepted ONLY on a local dev stack (manual
            # curl testing). Keyed off is_local_dev rather than ENVIRONMENT:
            # a deploy that forgot ENVIRONMENT=production must still reject
            # forged bounce/complaint events (they suppress real addresses).
            if not settings.is_local_dev:
                return False
            logger.warning("RESEND_WEBHOOK_SECRET not set — skipping signature verification")
            return True
        try:
            resend.Webhooks.verify(
                {
                    "payload": body.decode("utf-8"),
                    "headers": {
                        "id": headers.get("svix-id", ""),
                        "timestamp": headers.get("svix-timestamp", ""),
                        "signature": headers.get("svix-signature", ""),
                    },
                    "webhook_secret": settings.resend_webhook_secret,
                }
            )
            return True
        except (ValueError, UnicodeDecodeError):
            return False
