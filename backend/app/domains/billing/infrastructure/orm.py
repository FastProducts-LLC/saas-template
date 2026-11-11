"""Billing persistence mapping."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.billing.domain.entities import BillingAccount, Subscription
from app.domains.billing.domain.value_objects import BillingInterval, Plan, PlanSubscriptionStatus

billing_accounts_table = sa.Table(
    "billing_accounts",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("stripe_customer_id", sa.String(255), nullable=True, index=True),
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
    sa.UniqueConstraint("organization_id"),
)

Base.registry.map_imperatively(BillingAccount, billing_accounts_table)


def _str_enum(enum_cls, *, length: int):
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


subscriptions_table = sa.Table(
    "subscriptions",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    sa.Column("stripe_subscription_id", sa.String(255), nullable=False, unique=True),
    sa.Column("plan", _str_enum(Plan, length=32), nullable=False),
    sa.Column("interval", _str_enum(BillingInterval, length=16), nullable=False),
    sa.Column("status", _str_enum(PlanSubscriptionStatus, length=32), nullable=False),
    sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
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
)

Base.registry.map_imperatively(Subscription, subscriptions_table)
