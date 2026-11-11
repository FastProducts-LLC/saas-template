"""LLM persistence mapping: the `llm_calls` audit table."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.llm.domain.entities import LlmCall, LlmCallStatus, LlmProvider


def _enum_column(e, length: int = 16) -> sa.Enum:
    return sa.Enum(
        e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x]
    )


llm_calls_table = sa.Table(
    "llm_calls",
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
    sa.Column("provider", _enum_column(LlmProvider), nullable=False),
    sa.Column("model", sa.String(64), nullable=False),
    sa.Column("prompt", sa.Text(), nullable=False),
    sa.Column("status", _enum_column(LlmCallStatus), nullable=False),
    sa.Column(
        "reservation_id",
        sa.Uuid(),
        sa.ForeignKey("credit_reservations.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("response_text", sa.Text(), nullable=True),
    sa.Column("response_preview", sa.Text(), nullable=True),
    sa.Column("tokens_in", sa.Integer(), nullable=False),
    sa.Column("tokens_out", sa.Integer(), nullable=False),
    sa.Column("credits_cost", sa.Integer(), nullable=False),
    sa.Column("error", sa.Text(), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Index("ix_llm_calls_org_created", "organization_id", "created_at"),
)

Base.registry.map_imperatively(LlmCall, llm_calls_table)
