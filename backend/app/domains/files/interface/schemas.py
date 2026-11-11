"""Upload HTTP request and response shapes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.files.application.facade import FileService
from app.domains.files.domain.entities import FilePurpose, StoredFile, StoredFileStatus


class UploadCreate(BaseModel):
    purpose: FilePurpose
    content_type: str
    size_bytes: int = Field(gt=0)


class UploadTarget(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


class UploadCreated(BaseModel):
    file_id: uuid.UUID
    upload: UploadTarget


class FileOut(BaseModel):
    id: uuid.UUID
    purpose: FilePurpose
    content_type: str
    size_bytes: int | None
    status: StoredFileStatus
    url: str

    @classmethod
    def from_entity(cls, file: StoredFile) -> "FileOut":
        return cls(
            id=file.id,
            purpose=file.purpose,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            status=file.status,
            url=FileService.content_url(file),
        )
