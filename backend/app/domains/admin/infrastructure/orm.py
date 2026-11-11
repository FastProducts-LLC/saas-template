"""Admin persistence mapping: the platform-admin audit log."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.domains.admin.domain.entities import AdminAuditEntry

admin_audit_log_table = sa.Table(
    "admin_audit_log",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "actor_user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("target_type", sa.String(32), nullable=False),
    sa.Column("target_id", sa.Uuid(), nullable=True),
    sa.Column("meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        index=True,
    ),
)

Base.registry.map_imperatively(AdminAuditEntry, admin_audit_log_table)
