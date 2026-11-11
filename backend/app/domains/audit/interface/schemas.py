"""Audit API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    organization_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    ip: str | None
    user_agent: str | None
    meta: dict
    created_at: datetime
