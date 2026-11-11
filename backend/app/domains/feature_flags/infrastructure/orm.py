"""Feature-flag persistence mapping — table + imperative mapping."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.feature_flags.domain.entities import FeatureFlag

feature_flags_table = sa.Table(
    "feature_flags",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("key", sa.String(64), nullable=False, unique=True, index=True),
    sa.Column("enabled", sa.Boolean(), nullable=False),
    sa.Column(
        "updated_by",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

Base.registry.map_imperatively(FeatureFlag, feature_flags_table)
