"""Small file service exported to other slices via interface.deps."""

import logging
import re
import uuid

from app.core.storage import FileStorage, StorageError
from app.domains.files.application.ports import FileRepository
from app.domains.files.domain.entities import FilePurpose, StoredFile

logger = logging.getLogger(__name__)
CONTENT_URL_TEMPLATE = "/api/files/{file_id}/content"
_CONTENT_URL_RE = re.compile(
    re.escape(CONTENT_URL_TEMPLATE).replace(
        re.escape("{file_id}"),
        r"(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    )
)


class FileService:
    def __init__(self, files: FileRepository, storage: FileStorage) -> None:
        self.files = files
        self.storage = storage

    async def get_ready_file(self, file_id: uuid.UUID) -> StoredFile | None:
        file = await self.files.get(file_id)
        if file is not None and file.user_id is not None:
            await self.files.lock_owner(file.user_id)
            # A concurrent upload/cleanup may have changed the file while we waited.
            file = await self.files.get(file_id, lock=True)
        return file if file is not None and file.is_ready else None

    @staticmethod
    def content_url(file: StoredFile) -> str:
        return CONTENT_URL_TEMPLATE.format(file_id=file.id)

    @staticmethod
    def file_id_from_url(url: str) -> uuid.UUID | None:
        match = _CONTENT_URL_RE.fullmatch(url)
        return uuid.UUID(match["id"]) if match else None

    async def delete_file(self, file_id: uuid.UUID) -> None:
        file = await self.files.get(file_id, lock=True)
        if file is None:
            return
        try:
            await self.storage.delete(file.key)
        except StorageError as exc:
            # Never log object keys, signed URLs, or provider exception text.
            logger.warning("File object deletion failed: %s", type(exc).__name__)
        await self.files.delete(file)

    async def delete_owner_files(
        self, user_id: uuid.UUID, purpose: FilePurpose, *, keep: uuid.UUID | None
    ) -> int:
        await self.files.lock_owner(user_id)
        files = await self.files.list_for_owner(user_id, purpose)
        deleted = 0
        for file in files:
            if file.id != keep:
                await self.delete_file(file.id)
                deleted += 1
        return deleted

    async def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        files = await self.files.list_for_user(user_id)
        for file in files:
            await self.delete_file(file.id)
        return len(files)

    async def delete_all_for_org(self, org_id: uuid.UUID) -> int:
        files = await self.files.list_for_org(org_id)
        for file in files:
            await self.delete_file(file.id)
        return len(files)
