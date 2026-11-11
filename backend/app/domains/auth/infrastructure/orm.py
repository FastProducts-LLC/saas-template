"""Auth persistence mapping: tables + imperative mapping onto pure entities.

The domain entities know nothing about SQLAlchemy; this module attaches the
mapping at import time (idempotent — Python caches the module). Anything that
queries these entities must import this module first; repositories in this
package do, as does `alembic/env.py` for autogenerate.

Table/index names are identical to the previous declarative models, so this
refactor produces no schema migration.
"""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.auth.domain.entities import RefreshToken, User

users_table = sa.Table(
    "users",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("email", sa.String(320), nullable=False, unique=True, index=True),
    sa.Column("password_hash", sa.String(255), nullable=False),
    sa.Column("first_name", sa.String(60), nullable=False),
    sa.Column("last_name", sa.String(60), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False),
    sa.Column("is_superuser", sa.Boolean(), nullable=False),
    sa.Column("marketing_opt_in", sa.Boolean(), nullable=False),
    sa.Column("email_suppressed", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("analytics_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)

refresh_tokens_table = sa.Table(
    "refresh_tokens",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)

Base.registry.map_imperatively(User, users_table)
Base.registry.map_imperatively(RefreshToken, refresh_tokens_table)
