"""API keys persistence mapping — table + imperative mapping."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.api_keys.domain.entities import ApiKey

api_keys_table = sa.Table(
    "api_keys",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("key_prefix", sa.String(24), nullable=False),
    sa.Column("key_hash", sa.String(64), nullable=False, unique=True, index=True),
    sa.Column(
        "created_by_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)

Base.registry.map_imperatively(ApiKey, api_keys_table)
