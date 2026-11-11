"""Generations persistence mapping (table identical to before — no migration)."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.credits.domain import CreditAction
from app.domains.generations.domain.entities import Generation, GenerationStatus

generations_table = sa.Table(
    "generations",
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
        "kind",
        sa.Enum(
            CreditAction,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    ),
    sa.Column("model", sa.String(64), nullable=False),
    sa.Column("prompt", sa.Text(), nullable=False),
    sa.Column(
        "status",
        sa.Enum(
            GenerationStatus,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    ),
    sa.Column(
        "reservation_id",
        sa.Uuid(),
        sa.ForeignKey("credit_reservations.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("credits_cost", sa.Integer(), nullable=False),
    sa.Column("file_path", sa.String(255), nullable=True),
    sa.Column("mime_type", sa.String(64), nullable=True),
    sa.Column("error", sa.Text(), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Index("ix_generations_org_created", "organization_id", "created_at"),
)

Base.registry.map_imperatively(Generation, generations_table)
