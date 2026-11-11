"""add activity_events + users.analytics_opt_out

Revision ID: a7c41e9b2d10
Revises: cc23c8867cc3
Create Date: 2026-11-09 00:00:00.000000

First-party product analytics (domains/analytics). The table name and the
user_id / created_at columns are a contract with external DAU/retention
queries — index names follow that contract, not this repo's ix_ convention.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7c41e9b2d10"
down_revision: str | None = "cc23c8867cc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("analytics_opt_out", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "activity_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), server_default="client", nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('client', 'server')", name="activity_events_source_check"),
        # Account deletion purges the user's event trail.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("activity_events_created_at_idx", "activity_events", ["created_at"])
    op.create_index(
        "activity_events_user_created_idx", "activity_events", ["user_id", "created_at"]
    )
    op.create_index("activity_events_event_created_idx", "activity_events", ["event", "created_at"])


def downgrade() -> None:
    op.drop_index("activity_events_event_created_idx", table_name="activity_events")
    op.drop_index("activity_events_user_created_idx", table_name="activity_events")
    op.drop_index("activity_events_created_at_idx", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_column("users", "analytics_opt_out")
