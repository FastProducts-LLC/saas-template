"""Audit use cases."""

from datetime import UTC, datetime, timedelta

from app.domains.audit.application.ports import AuditEventRepository


class PurgeExpiredAuditEvents:
    """Delete events past the retention window (beat-scheduled)."""

    def __init__(self, events: AuditEventRepository, retention_days: int) -> None:
        self.events = events
        self.retention_days = retention_days

    async def execute(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        return await self.events.delete_older_than(cutoff)
