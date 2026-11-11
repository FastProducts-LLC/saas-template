"""Consent-event persistence — append-only audit trail."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.domains.consents.domain.entities import ConsentEvent

consent_events_table = sa.Table(
    "consent_events",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "categories",
        JSONB(),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column("policy_version", sa.String(32), nullable=False),
    sa.Column("ip_address", sa.String(45), nullable=True),
    sa.Column("user_agent", sa.String(255), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_consent_events_user_created", "user_id", "created_at"),
)

Base.registry.map_imperatively(ConsentEvent, consent_events_table)
