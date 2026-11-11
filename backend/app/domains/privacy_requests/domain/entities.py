"""Privacy / data-subject request entities (GDPR/CCPA DSAR intake).

Fulfillment is intentionally thin: an admin verifies, optionally forwards to
an upstream data processor, then marks fulfilled. We keep durable audit
metadata longer than the raw intake payload (see retention constants +
purge task).
"""

import enum
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Raw intake bodies (emails, phones, free-text) are purged after this window.
# Status, type, hashes, provider refs, and admin notes are kept longer.
REQUEST_PAYLOAD_RETENTION_DAYS = 90

# CCPA-style outer SLA used for admin deadline tracking (not a legal guarantee).
DEFAULT_DEADLINE_DAYS = 45


class PrivacyRequestType(str, enum.Enum):
    ACCESS = "access"
    DELETE = "delete"
    SUPPRESS = "suppress"


class PrivacyRequestStatus(str, enum.Enum):
    RECEIVED = "received"
    VERIFIED = "verified"
    FORWARDED = "forwarded"  # escalated to an upstream data processor
    FULFILLED = "fulfilled"  # request satisfied (+ provider forward if needed)
    CLOSED = "closed"
    REJECTED = "rejected"


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    value = email.strip().lower()
    return value or None


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    return digits or None


def identifier_hash(kind: str, value: str) -> str:
    """Stable one-way fingerprint for audit after payload purge.

    Not a security boundary — only so support can confirm "we had an email
    matching X" without retaining the raw value forever.
    """
    digest = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()
    return digest[:32]


@dataclass(eq=False)
class PrivacyRequest:
    """Data-subject (or authorized-agent) rights request."""

    request_type: PrivacyRequestType
    status: PrivacyRequestStatus = PrivacyRequestStatus.RECEIVED

    # Contact for response / verification (also used as a subject identifier).
    requester_email: str | None = None
    requester_name: str | None = None

    # Subject locators — cleared by the retention purge after REQUEST_PAYLOAD_RETENTION_DAYS.
    subject_email: str | None = None
    subject_phone: str | None = None
    subject_consumer_key: str | None = None
    subject_first_name: str | None = None
    subject_last_name: str | None = None
    # Free-text / extra fields from the public form. Purged with the locators.
    request_payload: dict[str, Any] = field(default_factory=dict)

    # Durable audit fingerprints (survive payload purge).
    subject_email_hash: str | None = None
    subject_phone_hash: str | None = None
    subject_consumer_key_hash: str | None = None

    # Ops / provider escalation
    admin_notes: str | None = None
    provider_reference: str | None = None
    provider_forwarded_at: datetime | None = None
    fulfilled_at: datetime | None = None
    fulfilled_by_user_id: uuid.UUID | None = None
    rejection_reason: str | None = None

    payload_purged_at: datetime | None = None
    ip_address: str | None = None
    deadline_at: datetime | None = None

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def stamp_identifier_hashes(self) -> None:
        email = normalize_email(self.subject_email) or normalize_email(self.requester_email)
        phone = normalize_phone(self.subject_phone)
        key = (self.subject_consumer_key or "").strip() or None
        if email:
            self.subject_email_hash = identifier_hash("email", email)
        if phone:
            self.subject_phone_hash = identifier_hash("phone", phone)
        if key:
            self.subject_consumer_key_hash = identifier_hash("consumer_key", key)

    def purge_raw_payload(self, *, now: datetime | None = None) -> bool:
        """Drop raw PII fields; keep status/hashes/provider audit. Idempotent."""
        if self.payload_purged_at is not None:
            return False
        self.requester_email = None
        self.requester_name = None
        self.subject_email = None
        self.subject_phone = None
        self.subject_consumer_key = None
        self.subject_first_name = None
        self.subject_last_name = None
        self.request_payload = {}
        self.ip_address = None
        self.payload_purged_at = now or _utcnow()
        self.updated_at = self.payload_purged_at
        return True

    @staticmethod
    def default_deadline(*, now: datetime | None = None) -> datetime:
        return (now or _utcnow()) + timedelta(days=DEFAULT_DEADLINE_DAYS)
