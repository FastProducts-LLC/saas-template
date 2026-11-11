"""File uploads and downloads; local upload grants carry their own authorization."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse

from app.core.config import settings
from app.core.error_handling import problem_response
from app.core.policy import RATE_LIMIT_FILES_UPLOAD
from app.core.ratelimit import limiter
from app.core.storage import StorageError
from app.core.storage.local import decode_upload_token
from app.domains.auth.interface.deps import CurrentUser
from app.domains.files.application import use_cases as uc
from app.domains.files.domain.errors import (
    FileNotFound,
    UnsupportedFileType,
    UploadQuotaExceeded,
    UploadTooLarge,
)
from app.domains.files.interface.deps import (
    LocalStorage,
    OptionalUser,
    get_confirm_upload,
    get_create_upload,
    get_read_content,
)
from app.domains.files.interface.schemas import FileOut, UploadCreate, UploadCreated, UploadTarget

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/uploads", response_model=UploadCreated, status_code=201)
@limiter.limit(RATE_LIMIT_FILES_UPLOAD)
async def create_upload(
    request: Request,
    response: Response,
    body: UploadCreate,
    user: CurrentUser,
    use_case: Annotated[uc.CreateUpload, Depends(get_create_upload)],
):
    try:
        file, upload = await use_case.execute(user.id, **body.model_dump())
    except UploadQuotaExceeded as exc:
        # Preserve superseded pending-file cleanup even when the quota is full.
        return problem_response(request, exc.internal_code, detail=exc.message)
    return UploadCreated(file_id=file.id, upload=UploadTarget.model_validate(upload))


@router.put("/local-upload/{token}", status_code=204)
async def local_upload(token: str, request: Request, storage: LocalStorage):
    if settings.storage_provider != "local":
        raise FileNotFound()
    try:
        grant = decode_upload_token(token)
    except StorageError as exc:
        raise FileNotFound() from exc
    if request.headers.get("content-type") != grant.content_type:
        raise UnsupportedFileType()
    length = request.headers.get("content-length")
    if length is not None:
        try:
            declared_length = int(length)
        except ValueError:
            declared_length = 0  # Still bounded below, even with a malformed header.
        if declared_length > grant.max_bytes:
            raise UploadTooLarge()
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > grant.max_bytes:
            raise UploadTooLarge()
        data.extend(chunk)
    with uc.storage_errors():
        await storage.put(grant.key, bytes(data), content_type=grant.content_type)
    return Response(status_code=204)


@router.post("/{file_id}/confirm", response_model=FileOut)
async def confirm_upload(
    file_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    use_case: Annotated[uc.ConfirmUpload, Depends(get_confirm_upload)],
):
    try:
        file = await use_case.execute(file_id, user.id)
    except (UploadTooLarge, UnsupportedFileType) as exc:
        # Returning the error lets get_db commit rejection cleanup. Raising it
        # would roll back the deleted row and leave a permanently pending file.
        return problem_response(request, exc.internal_code, detail=exc.message)
    return FileOut.from_entity(file)


@router.get("/{file_id}/content")
async def file_content(
    file_id: uuid.UUID,
    user: OptionalUser,
    use_case: Annotated[uc.ReadContent, Depends(get_read_content)],
):
    content = await use_case.execute(file_id, user.id if user else None)
    if content.redirect_url is not None:
        return RedirectResponse(
            content.redirect_url,
            status_code=307,
            headers={"Cache-Control": "private, max-age=60"},
        )
    data = content.data or b""
    return StreamingResponse(
        iter(data[offset : offset + 65536] for offset in range(0, len(data), 65536)),
        media_type=content.file.content_type,
        headers={
            "Cache-Control": "public, max-age=300" if content.public else "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
