"""Organization entitlement override persistence mapping."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.entitlements.domain.entities import EntitlementKey, EntitlementOverride


def _str_enum(enum_cls, *, length: int):
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


organization_entitlements_table = sa.Table(
    "organization_entitlements",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("key", _str_enum(EntitlementKey, length=64), nullable=False),
    sa.Column("limit_value", sa.Integer(), nullable=True),
    sa.Column("source", sa.String(32), nullable=False),
    sa.Column("note", sa.String(500), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_by_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    ),
    sa.UniqueConstraint("organization_id", "key", name="uq_organization_entitlements_org_key"),
)

Base.registry.map_imperatively(EntitlementOverride, organization_entitlements_table)
