"""API key HTTP schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.policy import API_KEY_NAME_MAX_LENGTH


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=API_KEY_NAME_MAX_LENGTH)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    """Returned exactly once at creation — includes the full raw key."""

    raw_key: str
