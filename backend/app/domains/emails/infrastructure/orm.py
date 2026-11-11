"""Emails persistence mapping: email_events table + imperative mapping."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.domains.emails.domain.entities import EmailEvent

email_events_table = sa.Table(
    "email_events",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    # Unique when present — dedupes Svix's at-least-once redeliveries; a
    # missing header must not block ingestion.
    sa.Column("svix_id", sa.String(64), nullable=True, unique=True),
    sa.Column("email_id", sa.String(64), nullable=False, server_default="", index=True),
    sa.Column("event", sa.String(30), nullable=False),
    sa.Column("recipient", sa.String(320), nullable=False, server_default=""),
    sa.Column("subject", sa.String(255), nullable=False, server_default=""),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Index("ix_email_events_event_received", "event", "received_at"),
    sa.Index("ix_email_events_recipient", "recipient"),
)

Base.registry.map_imperatively(EmailEvent, email_events_table)
