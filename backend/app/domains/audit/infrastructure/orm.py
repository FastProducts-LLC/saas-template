"""Audit persistence mapping: the security-event trail."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.domains.audit.domain.entities import AuditEvent

audit_events_table = sa.Table(
    "audit_events",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "actor_user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("target_type", sa.String(32), nullable=True),
    sa.Column("target_id", sa.Uuid(), nullable=True),
    sa.Column("ip", sa.String(45), nullable=True),  # INET6_ADDRSTRLEN
    sa.Column("user_agent", sa.String(256), nullable=True),
    sa.Column("meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    # Query patterns: time-window lists + retention purge, "all lockouts last
    # 24h", per-user timeline.
    sa.Index("ix_audit_events_created_at", "created_at"),
    sa.Index("ix_audit_events_action_created_at", "action", "created_at"),
    sa.Index("ix_audit_events_actor_created_at", "actor_user_id", "created_at"),
)

Base.registry.map_imperatively(AuditEvent, audit_events_table)
