"""Upload lifecycle and access rules. Transactions belong to composition roots."""

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.policy import UPLOAD_PRESIGN_TTL_SECONDS
from app.core.storage import (
    FileStorage,
    PresignedUpload,
    StorageError,
    StorageObjectNotFound,
    user_key,
)
from app.domains.files.application.ports import FileRepository, OrganizationQueries
from app.domains.files.domain.entities import FilePurpose, StoredFile
from app.domains.files.domain.errors import (
    FileNotFound,
    StorageUnavailable,
    UnsupportedFileType,
    UploadNotCompleted,
    UploadQuotaExceeded,
    UploadTooLarge,
)
from app.domains.files.domain.policy import CONTENT_TYPE_EXTENSIONS, FILE_RULES, sniff_image_type


@contextmanager
def storage_errors():
    try:
        yield
    except StorageError as exc:
        raise StorageUnavailable() from exc


class CreateUpload:
    def __init__(self, files: FileRepository, storage: FileStorage) -> None:
        self.files = files
        self.storage = storage

    async def execute(
        self, user_id: uuid.UUID, *, purpose: FilePurpose, content_type: str, size_bytes: int
    ) -> tuple[StoredFile, PresignedUpload]:
        rules = FILE_RULES[purpose]
        if content_type not in rules.content_types:
            raise UnsupportedFileType()
        if size_bytes <= 0:
            raise ValueError("Upload size must be positive")
        if size_bytes > rules.max_bytes:
            raise UploadTooLarge()
        # The user-upload endpoint only creates user-owned purposes.
        if rules.owner != "user":
            raise UnsupportedFileType()
        await self.files.lock_owner(user_id)
        owned_files = await self.files.list_for_owner(user_id, purpose)
        with storage_errors():
            for existing in owned_files:
                if not existing.is_ready:
                    await self.storage.delete(existing.key)
                    await self.files.delete(existing)
        if sum(file.is_ready for file in owned_files) >= rules.max_files_per_owner:
            raise UploadQuotaExceeded()
        extension = CONTENT_TYPE_EXTENSIONS[content_type]
        file = StoredFile(
            key=user_key(user_id, rules.area, f"{uuid.uuid4()}.{extension}"),
            purpose=purpose,
            content_type=content_type,
            created_by_id=user_id,
            user_id=user_id,
            size_bytes=size_bytes,
        )
        with storage_errors():
            upload = await self.storage.presigned_put(
                file.key,
                content_type=content_type,
                max_bytes=rules.max_bytes,
                ttl=timedelta(seconds=UPLOAD_PRESIGN_TTL_SECONDS),
            )
        await self.files.add(file)
        return file, upload


class ConfirmUpload:
    def __init__(self, files: FileRepository, storage: FileStorage) -> None:
        self.files = files
        self.storage = storage

    async def execute(self, file_id: uuid.UUID, user_id: uuid.UUID) -> StoredFile:
        await self.files.lock_owner(user_id)
        file = await self.files.get(file_id, lock=True)
        if file is None or file.created_by_id != user_id:
            raise FileNotFound()
        if file.is_ready:
            return file
        rules = FILE_RULES[file.purpose]
        with storage_errors():
            info = await self.storage.stat(file.key)
            if info is None:
                raise UploadNotCompleted()
            if info.size_bytes > rules.max_bytes:
                await self._reject(file, UploadTooLarge())
            try:
                data = await self.storage.get(file.key)
            except StorageObjectNotFound as exc:
                raise UploadNotCompleted() from exc
            # Check the fetched object too: it could have changed since stat.
            if len(data) > rules.max_bytes:
                await self._reject(file, UploadTooLarge())
            actual_type = sniff_image_type(data[:12])
            if actual_type not in rules.content_types or actual_type != file.content_type:
                await self._reject(file, UnsupportedFileType())
        file.confirm(size_bytes=len(data))
        return file

    async def _reject(self, file: StoredFile, error: UploadTooLarge | UnsupportedFileType) -> None:
        await self.storage.delete(file.key)
        await self.files.delete(file)
        raise error


@dataclass(frozen=True)
class FileContent:
    file: StoredFile
    public: bool
    redirect_url: str | None = None
    data: bytes | None = None


class ReadContent:
    def __init__(
        self, files: FileRepository, storage: FileStorage, organizations: OrganizationQueries
    ) -> None:
        self.files = files
        self.storage = storage
        self.organizations = organizations

    async def execute(self, file_id: uuid.UUID, user_id: uuid.UUID | None) -> FileContent:
        file = await self.files.get(file_id)
        if file is None or not file.is_ready:
            raise FileNotFound()
        public = FILE_RULES[file.purpose].public
        if not public:
            if user_id is None:
                raise FileNotFound()
            allowed = file.user_id == user_id
            if not allowed and file.organization_id is not None:
                allowed = any(
                    org.id == file.organization_id
                    for org, _ in await self.organizations.list_user_orgs(user_id)
                )
            if not allowed:
                raise FileNotFound()
        with storage_errors():
            url = await self.storage.presigned_get(
                file.key, ttl=timedelta(seconds=UPLOAD_PRESIGN_TTL_SECONDS)
            )
            if url is not None:
                return FileContent(file, public, redirect_url=url)
            data = await self.storage.get(file.key)
        return FileContent(file, public, data=data)


class DeleteStaleUpload:
    def __init__(self, files: FileRepository, storage: FileStorage) -> None:
        self.files = files
        self.storage = storage

    async def execute(self, file_id: uuid.UUID, cutoff: datetime) -> bool:
        file = await self.files.get(file_id, lock=True)
        if file is None or file.is_ready or file.created_at >= cutoff:
            return False
        # Keep the row on provider failure so a later run can retry the object.
        try:
            await self.storage.delete(file.key)
        except StorageObjectNotFound:
            pass
        await self.files.delete(file)
        return True
