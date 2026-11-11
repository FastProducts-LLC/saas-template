"""Public object storage contracts and key helpers."""

from app.core.storage.base import (
    FileStorage,
    ObjectInfo,
    PresignedUpload,
    StorageError,
    StorageObjectNotFound,
)
from app.core.storage.factory import get_file_storage
from app.core.storage.keys import org_key, user_key, validate_key
from app.core.storage.local import LocalFileStorage

__all__ = [
    "FileStorage",
    "get_file_storage",
    "LocalFileStorage",
    "S3FileStorage",
    "ObjectInfo",
    "PresignedUpload",
    "StorageError",
    "StorageObjectNotFound",
    "org_key",
    "user_key",
    "validate_key",
]


def __getattr__(name: str):
    if name == "S3FileStorage":
        from app.core.storage.s3 import S3FileStorage

        return S3FileStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
