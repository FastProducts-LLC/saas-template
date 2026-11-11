"""Stored file persistence mapping."""

import sqlalchemy as sa

from app.core.database import Base
from app.domains.files.domain.entities import FilePurpose, StoredFile, StoredFileStatus


def _str_enum(enum_cls, *, length: int):
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


stored_files_table = sa.Table(
    "stored_files",
    Base.metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "organization_id",
        sa.Uuid(),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    sa.Column(
        "user_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    ),
    sa.Column("purpose", _str_enum(FilePurpose, length=32), nullable=False),
    sa.Column("key", sa.String(512), nullable=False, unique=True),
    sa.Column("content_type", sa.String(128), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=True),
    sa.Column("status", _str_enum(StoredFileStatus, length=16), nullable=False),
    sa.Column(
        "created_by_id",
        sa.Uuid(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    ),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "organization_id IS NOT NULL OR user_id IS NOT NULL",
        name="ck_stored_files_has_owner",
    ),
    sa.Index("ix_stored_files_status_created_at", "status", "created_at"),
)

Base.registry.map_imperatively(StoredFile, stored_files_table)
