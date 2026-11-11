"""Generation media adapter over the shared object storage port."""

import uuid
from datetime import timedelta

from app.core.policy import UPLOAD_PRESIGN_TTL_SECONDS
from app.core.storage import FileStorage, get_file_storage, org_key
from app.core.storage.base import StorageError, StorageObjectNotFound
from app.domains.files.domain.errors import StorageUnavailable
from app.domains.generations.application.dtos import MediaDownload, MediaFileUrl
from app.domains.generations.domain import GeneratedAsset, GenerationNotFound

_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "video/mp4": "mp4"}


class StorageMediaStore:
    def __init__(self, storage: FileStorage | None = None) -> None:
        self.storage = storage if storage is not None else get_file_storage()

    async def save(self, org_id: uuid.UUID, name: str, asset: GeneratedAsset) -> str:
        key = org_key(org_id, "generations", name)
        if len(key) > 255:
            raise ValueError("Generation storage key exceeds the file_path column length")
        await self.storage.put(key, asset.data, content_type=asset.mime_type)
        return key

    async def download(self, file_path: str, mime_type: str) -> MediaDownload:
        try:
            return MediaDownload(mime_type=mime_type, data=await self.storage.get(file_path))
        except StorageObjectNotFound as exc:
            raise GenerationNotFound("Result file is missing from storage.") from exc
        except StorageError as exc:
            raise StorageUnavailable("Result storage is temporarily unavailable.") from exc

    async def file_url(self, file_path: str) -> MediaFileUrl:
        try:
            if await self.storage.stat(file_path) is None:
                raise StorageObjectNotFound("Storage object not found")
            url = await self.storage.presigned_get(
                file_path, ttl=timedelta(seconds=UPLOAD_PRESIGN_TTL_SECONDS)
            )
            return MediaFileUrl(
                url=url, expires_in=UPLOAD_PRESIGN_TTL_SECONDS if url is not None else None
            )
        except StorageObjectNotFound as exc:
            raise GenerationNotFound("Result file is missing from storage.") from exc
        except StorageError as exc:
            raise StorageUnavailable("Result storage is temporarily unavailable.") from exc

    async def delete(self, file_path: str) -> None:
        # DeleteGeneration handles failures best-effort for both adapters.
        await self.storage.delete(file_path)

    def extension_for(self, mime_type: str) -> str:
        return _EXTENSIONS.get(mime_type, "bin")


# Preserve the import used by existing callers while selecting the configured provider.
LocalMediaStore = StorageMediaStore
