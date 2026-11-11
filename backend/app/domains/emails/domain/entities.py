"""Emails domain entities — pure Python, zero framework/ORM imports."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class EmailEvent:
    """One provider webhook email event (sent/delivered/opened/bounced/…).

    Owning this log means deliverability and engagement data survives a
    provider switch, and gives a per-recipient timeline for "did they get
    it?" debugging. Deduped by the Svix message id — webhook delivery is
    at-least-once.
    """

    event: str
    recipient: str = ""
    subject: str = ""
    email_id: str = ""  # Resend's id for the sent email
    svix_id: str | None = None  # Svix delivery id; None when the header is absent
    occurred_at: datetime | None = None  # from the payload, when parseable
    payload: dict = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    received_at: datetime = field(default_factory=_utcnow)
