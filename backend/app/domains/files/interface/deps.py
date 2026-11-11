"""Files composition root and cross-slice facade builder."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.storage import FileStorage, get_file_storage
from app.domains.auth.domain import User
from app.domains.auth.interface.deps import get_current_user
from app.domains.files.application import use_cases as uc
from app.domains.files.application.facade import FileService
from app.domains.files.domain.errors import FileNotFound
from app.domains.files.infrastructure.repositories import SqlAlchemyFileRepository
from app.domains.organizations.interface.deps import get_org_queries

DB = Annotated[AsyncSession, Depends(get_db)]
Storage = Annotated[FileStorage, Depends(get_file_storage)]
_bearer = HTTPBearer(auto_error=False)


def build_file_service(db: AsyncSession) -> FileService:
    return FileService(SqlAlchemyFileRepository(db), get_file_storage())


def build_pending_upload_cleanup(db: AsyncSession) -> uc.DeleteStaleUpload:
    return uc.DeleteStaleUpload(SqlAlchemyFileRepository(db), get_file_storage())


def get_create_upload(db: DB, storage: Storage) -> uc.CreateUpload:
    return uc.CreateUpload(SqlAlchemyFileRepository(db), storage)


def get_confirm_upload(db: DB, storage: Storage) -> uc.ConfirmUpload:
    return uc.ConfirmUpload(SqlAlchemyFileRepository(db), storage)


def get_read_content(db: DB, storage: Storage) -> uc.ReadContent:
    return uc.ReadContent(SqlAlchemyFileRepository(db), storage, get_org_queries(db))


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], db: DB
) -> User | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except AuthenticationError:
        # Public content needs no valid session; private content masks auth failures as 404.
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_local_upload_storage() -> FileStorage:
    # Check before building the provider: S3 configuration must never affect this route.
    if settings.storage_provider != "local":
        raise FileNotFound()
    return get_file_storage()


LocalStorage = Annotated[FileStorage, Depends(get_local_upload_storage)]
