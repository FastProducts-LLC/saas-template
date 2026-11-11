"""Analytics domain — public surface for other slices."""

from app.domains.analytics.domain.entities import ActivityEvent
from app.domains.analytics.domain.events import CLIENT_EVENTS, SERVER_EVENTS

__all__ = ["CLIENT_EVENTS", "SERVER_EVENTS", "ActivityEvent"]
