"""Analytics persistence mapping: the first-party activity log.

The table name, `user_id`, and `created_at` are an external contract (DAU /
retention queries read them) — index names follow that contract rather than
this repo's `ix_` convention. ON DELETE CASCADE: deleting an account purges
its event trail.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.domains.analytics.domain import ActivityEvent

activity_events_table = sa.Table(
    "activity_events",
    Base.metadata,
    sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("event", sa.Text(), nullable=False),
    sa.Column("source", sa.Text(), nullable=False, server_default="client"),
    sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.CheckConstraint("source IN ('client', 'server')", name="activity_events_source_check"),
    # Time-window scans + retention purge; per-user timelines (DAU/retention);
    # funnel queries by event.
    sa.Index("activity_events_created_at_idx", "created_at"),
    sa.Index("activity_events_user_created_idx", "user_id", "created_at"),
    sa.Index("activity_events_event_created_idx", "event", "created_at"),
)

Base.registry.map_imperatively(ActivityEvent, activity_events_table)
