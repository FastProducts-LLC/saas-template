"""Audit HTTP endpoints — superuser only.

Read-only: events are written by the recorder inside other slices' flows,
never through HTTP.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.policy import ADMIN_PAGE_SIZE
from app.domains.admin.interface.deps import CurrentSuperuser
from app.domains.admin.interface.schemas import Page
from app.domains.audit.infrastructure.repositories import SqlAlchemyAuditEventRepository
from app.domains.audit.interface.schemas import AuditEventOut

router = APIRouter(prefix="/admin/audit-events", tags=["admin"])

DB = Annotated[AsyncSession, Depends(get_db)]
PageParam = Annotated[int, Query(ge=1)]
PageSizeParam = Annotated[int, Query(ge=1, le=100)]


@router.get("", response_model=Page[AuditEventOut])
async def list_audit_events(
    _: CurrentSuperuser,
    db: DB,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_user_id: uuid.UUID | None = None,
    page: PageParam = 1,
    page_size: PageSizeParam = ADMIN_PAGE_SIZE,
):
    repo = SqlAlchemyAuditEventRepository(db)
    rows, total = await repo.list_events(
        action=action,
        actor_user_id=actor_user_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[
            AuditEventOut(
                id=event.id,
                actor_user_id=event.actor_user_id,
                actor_email=email,
                organization_id=event.organization_id,
                action=event.action,
                target_type=event.target_type,
                target_id=event.target_id,
                ip=event.ip,
                user_agent=event.user_agent,
                meta=event.meta,
                created_at=event.created_at,
            )
            for event, email in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
