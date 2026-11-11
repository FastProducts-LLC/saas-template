"""Generations composition root."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.storage import FileStorage, get_file_storage
from app.domains.analytics.interface.deps import build_activity_tracker
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.generations.application.ports import MediaStore
from app.domains.generations.application.use_cases import (
    CancelGeneration,
    DeleteGeneration,
    DownloadGeneration,
    GetGenerationFileUrl,
    StartGeneration,
)
from app.domains.generations.infrastructure.media_store import LocalMediaStore
from app.domains.generations.infrastructure.providers import DispatchingProviderGateway
from app.domains.generations.infrastructure.repositories import SqlAlchemyGenerationRepository

DB = Annotated[AsyncSession, Depends(get_db)]

_providers = DispatchingProviderGateway()


def get_generation_repository(db: DB) -> SqlAlchemyGenerationRepository:
    return SqlAlchemyGenerationRepository(db)


def get_media_store(
    storage: Annotated[FileStorage | None, Depends(get_file_storage)] = None,
) -> LocalMediaStore:
    return LocalMediaStore(storage)


def get_start_generation(db: DB) -> StartGeneration:
    return StartGeneration(
        SqlAlchemyGenerationRepository(db),
        build_credit_engine(db),
        _providers,
        build_activity_tracker(db),
    )


def get_cancel_generation(db: DB) -> CancelGeneration:
    return CancelGeneration(SqlAlchemyGenerationRepository(db), build_credit_engine(db))


def get_download_generation(
    db: DB, media: Annotated[MediaStore, Depends(get_media_store)]
) -> DownloadGeneration:
    return DownloadGeneration(SqlAlchemyGenerationRepository(db), media)


def get_delete_generation(
    db: DB, media: Annotated[MediaStore, Depends(get_media_store)]
) -> DeleteGeneration:
    return DeleteGeneration(SqlAlchemyGenerationRepository(db), media)


def get_generation_file_url(
    db: DB, media: Annotated[MediaStore, Depends(get_media_store)]
) -> GetGenerationFileUrl:
    return GetGenerationFileUrl(SqlAlchemyGenerationRepository(db), media)
