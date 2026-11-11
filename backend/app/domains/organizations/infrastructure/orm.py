"""Organizations persistence mapping (tables identical to the previous
declarative models — no schema migration)."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.organizations.domain.entities import Invitation, Membership, Organization, Role


def _role_column() -> sa.Enum:
    return sa.Enum(
        Role, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
    )


organizations_table = sa.Table(
    "organizations",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
    sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("email_domain", sa.String(253), nullable=True, unique=True, index=True),
    sa.Column("intended_use", sa.String(500), nullable=False, server_default=""),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)

memberships_table = sa.Table(
    "memberships",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("role", _role_column(), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.UniqueConstraint("organization_id", "user_id"),
)

invitations_table = sa.Table(
    "invitations",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("email", sa.String(320), nullable=False, index=True),
    sa.Column("role", _role_column(), nullable=False),
    sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
    sa.Column(
        "invited_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    ),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
)

Base.registry.map_imperatively(Organization, organizations_table)
Base.registry.map_imperatively(Membership, memberships_table)
Base.registry.map_imperatively(Invitation, invitations_table)
