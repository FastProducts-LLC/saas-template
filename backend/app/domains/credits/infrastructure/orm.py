"""Credits persistence mapping."""

import enum

import sqlalchemy as sa

from app.core.database import Base
from app.domains.credits.domain.entities import (
    CreditAction,
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    MemberCreditLimit,
    ReservationStatus,
    TransactionType,
)


def _enum_column(e: type[enum.Enum], length: int = 32) -> sa.Enum:
    return sa.Enum(
        e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x]
    )


credit_wallets_table = sa.Table(
    "credit_wallets",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column("balance", sa.BigInteger(), nullable=False),
    sa.Column("allowance_period", sa.String(7), nullable=True),
    sa.Column("low_balance_notified_period", sa.String(7), nullable=True),
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

credit_reservations_table = sa.Table(
    "credit_reservations",
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
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    sa.Column(
        "api_key_id",
        sa.Uuid(),
        sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("action", _enum_column(CreditAction), nullable=False),
    sa.Column("amount", sa.BigInteger(), nullable=False),
    sa.Column("status", _enum_column(ReservationStatus, length=16), nullable=False),
    sa.Column("reference", sa.Text(), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Index("ix_credit_reservations_org_status", "organization_id", "status"),
    # Per-member limit sums (org + user + period range).
    sa.Index(
        "ix_credit_reservations_org_user_created",
        "organization_id",
        "user_id",
        "created_at",
    ),
    # Usage rollups (org + period range, all actors).
    sa.Index("ix_credit_reservations_org_created", "organization_id", "created_at"),
)

credit_transactions_table = sa.Table(
    "credit_transactions",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    sa.Column(
        "api_key_id",
        sa.Uuid(),
        sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "reservation_id",
        sa.Uuid(),
        sa.ForeignKey("credit_reservations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    sa.Column("type", _enum_column(TransactionType, length=16), nullable=False),
    sa.Column("action", _enum_column(CreditAction), nullable=True),
    sa.Column("amount", sa.BigInteger(), nullable=False),
    sa.Column("balance_after", sa.BigInteger(), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("idempotency_key", sa.String(255), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Index("ix_credit_transactions_org_created", "organization_id", "created_at"),
    # Webhook-redelivery guard: at most one grant per external event id.
    sa.Index(
        "uq_credit_transactions_idempotency_key",
        "idempotency_key",
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    ),
    # Per-user / per-key ledger rollups.
    sa.Index(
        "ix_credit_transactions_org_user_created",
        "organization_id",
        "user_id",
        "created_at",
    ),
    sa.Index(
        "ix_credit_transactions_org_api_key_created",
        "organization_id",
        "api_key_id",
        "created_at",
        postgresql_where=sa.text("api_key_id IS NOT NULL"),
    ),
)

member_credit_limits_table = sa.Table(
    "member_credit_limits",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    # CASCADE (not SET NULL): a deleted user's limit is meaningless.
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("monthly_limit", sa.BigInteger(), nullable=False),
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
    sa.UniqueConstraint("organization_id", "user_id", name="uq_member_credit_limits_org_user"),
)

Base.registry.map_imperatively(CreditWallet, credit_wallets_table)
Base.registry.map_imperatively(CreditReservation, credit_reservations_table)
Base.registry.map_imperatively(CreditTransaction, credit_transactions_table)
Base.registry.map_imperatively(MemberCreditLimit, member_credit_limits_table)
