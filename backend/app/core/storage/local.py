"""Atomic local object storage and purpose-bound upload grants."""

import asyncio
import mimetypes
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

from app.core.config import settings
from app.core.storage.base import (
    ObjectInfo,
    PresignedUpload,
    StorageError,
    StorageObjectNotFound,
)
from app.core.storage.keys import validate_key

_UPLOAD_PURPOSE = "local-file-upload"
_UPLOAD_AUDIENCE = "local-file-upload"
_UPLOAD_URL_PREFIX = "/api/files/local-upload/"


@dataclass(frozen=True)
class LocalUploadGrant:
    key: str
    content_type: str
    max_bytes: int
    expires_at: datetime


def decode_upload_token(token: str) -> LocalUploadGrant:
    """Verify a local upload JWT, refusing all other app token types."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            audience=_UPLOAD_AUDIENCE,
            options={"require": ["aud", "purpose", "key", "content_type", "max_bytes", "exp"]},
        )
        if (
            payload["purpose"] != _UPLOAD_PURPOSE
            or not isinstance(payload["key"], str)
            or not isinstance(payload["content_type"], str)
            or not payload["content_type"]
            or type(payload["max_bytes"]) is not int
            or payload["max_bytes"] < 0
            or type(payload["exp"]) is not int
        ):
            raise ValueError("Malformed upload grant")
        return LocalUploadGrant(
            key=validate_key(payload["key"]),
            content_type=payload["content_type"],
            max_bytes=payload["max_bytes"],
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError, OSError) as exc:
        raise StorageError("Invalid or expired upload grant") from exc


class LocalFileStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage key escapes the storage root")
        return path

    async def _run(self, key: str, operation):
        validate_key(key)

        def run():
            try:
                return operation(self._path(key))
            except OSError as exc:
                raise StorageError("Local storage operation failed") from exc

        return await asyncio.to_thread(run)

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        def write(path: Path):
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        await self._run(key, write)

    async def get(self, key: str) -> bytes:
        def read(path: Path):
            try:
                return path.read_bytes()
            except FileNotFoundError as exc:
                raise StorageObjectNotFound("Storage object not found") from exc

        return await self._run(key, read)

    async def delete(self, key: str) -> None:
        await self._run(key, lambda path: path.unlink(missing_ok=True))

    async def stat(self, key: str) -> ObjectInfo | None:
        def inspect(path: Path):
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                return None
            return ObjectInfo(key, size, mimetypes.guess_type(key)[0])

        return await self._run(key, inspect)

    async def presigned_get(
        self, key: str, *, ttl: timedelta, filename: str | None = None
    ) -> str | None:
        return await self._run(key, lambda path: None)

    async def presigned_put(
        self, key: str, *, content_type: str, max_bytes: int, ttl: timedelta
    ) -> PresignedUpload:
        await self._run(key, lambda path: None)
        expires_at = datetime.fromtimestamp(int((datetime.now(UTC) + ttl).timestamp()), UTC)
        token = jwt.encode(
            {
                "aud": _UPLOAD_AUDIENCE,
                "purpose": _UPLOAD_PURPOSE,
                "key": key,
                "content_type": content_type,
                "max_bytes": max_bytes,
                "exp": expires_at,
            },
            settings.secret_key,
            algorithm="HS256",
        )
        return PresignedUpload(
            url=f"{_UPLOAD_URL_PREFIX}{token}",
            method="PUT",
            headers={"Content-Type": content_type},
            expires_at=expires_at,
        )
