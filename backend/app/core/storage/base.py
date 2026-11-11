"""Provider-neutral object storage contracts; no SDK dependencies."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class StorageError(Exception):
    """An object storage operation failed."""


class StorageObjectNotFound(StorageError):
    """The requested object does not exist."""


@dataclass(frozen=True)
class ObjectInfo:
    key: str
    size_bytes: int
    content_type: str | None


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    method: str  # "PUT"
    headers: dict[str, str]  # headers the client must send with the upload
    expires_at: datetime  # timezone-aware UTC


class FileStorage(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes:
        """Raise StorageObjectNotFound when the key is missing."""
        ...

    async def delete(self, key: str) -> None:
        """Delete idempotently; a missing key is not an error."""
        ...

    async def stat(self, key: str) -> ObjectInfo | None:
        """Return None when the key is missing."""
        ...

    async def presigned_get(
        self, key: str, *, ttl: timedelta, filename: str | None = None
    ) -> str | None:
        """Return None when downloads must be streamed by the API."""
        ...

    async def presigned_put(
        self, key: str, *, content_type: str, max_bytes: int, ttl: timedelta
    ) -> PresignedUpload: ...
