"""Generations HTTP endpoints: create (credits held), poll, and download."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status

from app.core.policy import RATE_LIMIT_GENERATIONS_CREATE
from app.core.ratelimit import limiter
from app.domains.auth.interface.deps import CurrentVerifiedUser
from app.domains.generations.application.use_cases import (
    CancelGeneration,
    DeleteGeneration,
    DownloadGeneration,
    GetGenerationFileUrl,
    StartGeneration,
)
from app.domains.generations.domain import GenerationNotFound
from app.domains.generations.infrastructure.repositories import SqlAlchemyGenerationRepository
from app.domains.generations.interface.deps import (
    get_cancel_generation,
    get_delete_generation,
    get_download_generation,
    get_generation_file_url,
    get_generation_repository,
    get_start_generation,
)
from app.domains.generations.interface.schemas import (
    CreateGenerationRequest,
    GenerationFileUrlOut,
    GenerationOut,
)
from app.domains.generations.worker import enqueue_generation
from app.domains.organizations.interface.deps import CurrentMember

router = APIRouter(tags=["generations"])

Repo = Annotated[SqlAlchemyGenerationRepository, Depends(get_generation_repository)]


@router.post("/orgs/{org_id}/generations", response_model=GenerationOut, status_code=202)
@limiter.limit(RATE_LIMIT_GENERATIONS_CREATE)
async def create_generation(
    request: Request,
    response: Response,
    payload: CreateGenerationRequest,
    membership: CurrentMember,
    user: CurrentVerifiedUser,
    background: BackgroundTasks,
    use_case: Annotated[StartGeneration, Depends(get_start_generation)],
):
    generation = await use_case.execute(
        membership.organization_id, user.id, payload.kind, payload.prompt
    )
    # Enqueued after the request transaction commits; the worker finalizes
    # the job and its credit hold in its own session.
    background.add_task(enqueue_generation, generation.id)
    return GenerationOut.from_entity(generation)


@router.get("/orgs/{org_id}/generations", response_model=list[GenerationOut])
async def list_generations(
    membership: CurrentMember,
    repo: Repo,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items = await repo.list_for_org(membership.organization_id, limit=limit, offset=offset)
    return [GenerationOut.from_entity(g) for g in items]


@router.get("/orgs/{org_id}/generations/{generation_id}", response_model=GenerationOut)
async def get_generation(generation_id: uuid.UUID, membership: CurrentMember, repo: Repo):
    generation = await repo.get_for_org(membership.organization_id, generation_id)
    if generation is None:
        raise GenerationNotFound("Generation not found.")
    return GenerationOut.from_entity(generation)


@router.get("/orgs/{org_id}/generations/{generation_id}/file")
async def download_generation(
    generation_id: uuid.UUID,
    membership: CurrentMember,
    use_case: Annotated[DownloadGeneration, Depends(get_download_generation)],
):
    download = await use_case.execute(membership.organization_id, generation_id)
    return Response(content=download.data, media_type=download.mime_type)


@router.get(
    "/orgs/{org_id}/generations/{generation_id}/file-url", response_model=GenerationFileUrlOut
)
async def get_generation_file_url_endpoint(
    generation_id: uuid.UUID,
    membership: CurrentMember,
    response: Response,
    use_case: Annotated[GetGenerationFileUrl, Depends(get_generation_file_url)],
):
    result = await use_case.execute(membership.organization_id, generation_id)
    response.headers["Cache-Control"] = "no-store"
    return GenerationFileUrlOut(url=result.url, expires_in=result.expires_in)


@router.post("/orgs/{org_id}/generations/{generation_id}/cancel", response_model=GenerationOut)
async def cancel_generation(
    generation_id: uuid.UUID,
    membership: CurrentMember,
    use_case: Annotated[CancelGeneration, Depends(get_cancel_generation)],
):
    generation = await use_case.execute(membership.organization_id, generation_id)
    return GenerationOut.from_entity(generation)


@router.delete(
    "/orgs/{org_id}/generations/{generation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_generation(
    generation_id: uuid.UUID,
    membership: CurrentMember,
    use_case: Annotated[DeleteGeneration, Depends(get_delete_generation)],
):
    await use_case.execute(membership.organization_id, generation_id)
