"""Privacy-request persistence.

`privacy_requests.request_payload` and subject locator columns are short-lived
PII (purged by the retention beat task). Hashes, status, and provider refs
remain for audit.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.domains.privacy_requests.domain.entities import (
    PrivacyRequest,
    PrivacyRequestStatus,
    PrivacyRequestType,
)


def _str_enum(enum_cls, *, length: int):
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


privacy_requests_table = sa.Table(
    "privacy_requests",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("request_type", _str_enum(PrivacyRequestType, length=16), nullable=False),
    sa.Column("status", _str_enum(PrivacyRequestStatus, length=16), nullable=False, index=True),
    # Contact / subject locators — purged after REQUEST_PAYLOAD_RETENTION_DAYS.
    sa.Column("requester_email", sa.String(255), nullable=True),
    sa.Column("requester_name", sa.String(255), nullable=True),
    sa.Column("subject_email", sa.String(255), nullable=True),
    sa.Column("subject_phone", sa.String(32), nullable=True),
    sa.Column("subject_consumer_key", sa.String(64), nullable=True),
    sa.Column("subject_first_name", sa.String(128), nullable=True),
    sa.Column("subject_last_name", sa.String(128), nullable=True),
    sa.Column(
        "request_payload",
        JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
    # Durable fingerprints (survive payload purge).
    sa.Column("subject_email_hash", sa.String(32), nullable=True),
    sa.Column("subject_phone_hash", sa.String(32), nullable=True),
    sa.Column("subject_consumer_key_hash", sa.String(32), nullable=True),
    # Ops / provider
    sa.Column("admin_notes", sa.Text(), nullable=True),
    sa.Column("provider_reference", sa.String(128), nullable=True),
    sa.Column("provider_forwarded_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "fulfilled_by_user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("rejection_reason", sa.Text(), nullable=True),
    sa.Column("payload_purged_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("ip_address", sa.String(45), nullable=True),
    sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        index=True,
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_privacy_requests_type_status", "request_type", "status"),
)

Base.registry.map_imperatively(PrivacyRequest, privacy_requests_table)
