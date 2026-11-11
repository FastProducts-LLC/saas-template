"""Upload API contract exercised with real metadata persistence and temporary storage."""

import asyncio
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.policy import (
    UPLOAD_AVATAR_MAX_BYTES,
    UPLOAD_AVATAR_MAX_FILES,
    UPLOAD_PRESIGN_TTL_SECONDS,
)
from app.core.storage import StorageError, get_file_storage, user_key
from app.core.storage.factory import reset_file_storage_cache
from app.core.storage.local import decode_upload_token
from app.domains.files.application.facade import FileService
from app.domains.files.domain.entities import FilePurpose, StoredFile
from app.domains.files.domain.policy import FILE_RULES, sniff_image_type
from tests.helpers import create_org, register_and_login

PNG = b"\x89PNG\r\n\x1a\n" + b"test image bytes"
JPEG = b"\xff\xd8\xff" + b"test image bytes"
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"test image bytes"
UPLOADS = "/api/files/uploads"


@pytest.fixture(autouse=True)
def storage(monkeypatch, tmp_path):
    reset_file_storage_cache()
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    yield get_file_storage()
    reset_file_storage_cache()


@pytest.fixture
async def account(client):
    return await register_and_login(client)


async def create_upload(client, headers, **overrides):
    body = {"purpose": "avatar", "content_type": "image/png", "size_bytes": len(PNG)}
    body.update(overrides)
    return await client.post(UPLOADS, json=body, headers=headers)


async def upload_slot(client, headers, **overrides):
    response = await create_upload(client, headers, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


async def ready_upload(client, headers, *, data=PNG, content_type="image/png"):
    slot = await upload_slot(client, headers, content_type=content_type, size_bytes=len(data))
    response = await client.put(
        slot["upload"]["url"], content=data, headers=slot["upload"]["headers"]
    )
    assert response.status_code == 204, response.text
    response = await client.post(confirm_url(slot), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def confirm_url(slot):
    return f"/api/files/{slot['file_id']}/confirm"


def content_url(file_id):
    return f"/api/files/{file_id}/content"


async def stored_file(db, file_id):
    return await db.scalar(select(StoredFile).where(StoredFile.id == uuid.UUID(file_id)))


async def test_create_upload_returns_presigned_put(client, db, account):
    user, headers = account
    slot = await upload_slot(client, headers)
    target = slot["upload"]
    assert target["method"] == "PUT"
    assert target["headers"] == {"Content-Type": "image/png"}
    expires = datetime.fromisoformat(target["expires_at"].replace("Z", "+00:00"))
    assert 0 < (expires - datetime.now(UTC)).total_seconds() <= UPLOAD_PRESIGN_TTL_SECONDS
    grant = decode_upload_token(target["url"].rsplit("/", 1)[1])
    file = await stored_file(db, slot["file_id"])
    assert file.status == "pending" and file.user_id == uuid.UUID(user["id"])
    assert file.organization_id is None and file.created_by_id == file.user_id
    assert grant.key == file.key and grant.max_bytes == UPLOAD_AVATAR_MAX_BYTES
    assert grant.content_type == file.content_type == "image/png"


async def test_create_upload_requires_auth(client):
    response = await create_upload(client, {})
    assert response.status_code == 401


@pytest.mark.parametrize("content_type", ["image/svg+xml", "text/plain", "image/png/../../x"])
async def test_create_upload_rejects_unsupported_type(client, account, content_type):
    response = await create_upload(client, account[1], content_type=content_type)
    assert response.status_code == 415
    assert response.json()["code"] == "ERR_FILE_003"


async def test_create_upload_rejects_oversize_declared(client, account):
    response = await create_upload(client, account[1], size_bytes=UPLOAD_AVATAR_MAX_BYTES + 1)
    assert response.status_code == 413
    assert response.json()["code"] == "ERR_FILE_002"


@pytest.mark.parametrize("size", [0, -1])
async def test_create_upload_rejects_non_positive_size(client, account, size):
    response = await create_upload(client, account[1], size_bytes=size)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "data,content_type", [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")]
)
async def test_local_upload_then_confirm_marks_ready(client, db, account, data, content_type):
    slot = await upload_slot(client, account[1], size_bytes=1, content_type=content_type)
    response = await client.put(
        slot["upload"]["url"], content=data, headers=slot["upload"]["headers"]
    )
    assert response.status_code == 204
    # A second upload under the same grant overwrites the object.
    data += b"replacement"
    response = await client.put(
        slot["upload"]["url"], content=data, headers=slot["upload"]["headers"]
    )
    assert response.status_code == 204
    response = await client.post(confirm_url(slot), headers=account[1])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "id": slot["file_id"],
        "purpose": "avatar",
        "content_type": content_type,
        "size_bytes": len(data),
        "status": "ready",
        "url": content_url(slot["file_id"]),
    }
    file = await stored_file(db, slot["file_id"])
    assert file.is_ready and file.confirmed_at is not None
    assert (await client.get(body["url"])).content == data


async def test_local_upload_rejects_bad_token(client):
    response = await client.put(
        "/api/files/local-upload/invalid", content=PNG, headers={"Content-Type": "image/png"}
    )
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"


async def test_local_upload_rejects_expired_token(client, storage):
    target = await storage.presigned_put(
        user_key(uuid.uuid4(), "avatars", "expired.png"),
        content_type="image/png",
        max_bytes=len(PNG),
        ttl=timedelta(seconds=-1),
    )
    response = await client.put(target.url, content=PNG, headers=target.headers)
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"


async def test_local_upload_rejects_wrong_content_type(client, account, storage):
    slot = await upload_slot(client, account[1])
    response = await client.put(
        slot["upload"]["url"], content=PNG, headers={"Content-Type": "image/jpeg"}
    )
    assert response.status_code == 415
    grant = decode_upload_token(slot["upload"]["url"].rsplit("/", 1)[1])
    assert await storage.stat(grant.key) is None


@pytest.mark.parametrize("chunked", [False, True])
async def test_local_upload_rejects_body_over_limit(client, storage, chunked):
    key = user_key(uuid.uuid4(), "avatars", "bounded.png")
    target = await storage.presigned_put(
        key, content_type="image/png", max_bytes=8, ttl=timedelta(minutes=1)
    )
    consumed_tail = False

    async def chunks():
        nonlocal consumed_tail
        yield b"12345678"
        yield b"9"
        consumed_tail = True
        yield b"must not be read"

    response = await client.put(
        target.url, content=chunks() if chunked else b"123456789", headers=target.headers
    )
    assert response.status_code == 413, response.text
    assert not consumed_tail
    assert await storage.stat(key) is None


async def test_local_upload_is_404_when_provider_is_s3(client, account, monkeypatch):
    slot = await upload_slot(client, account[1])
    monkeypatch.setattr(settings, "storage_provider", "s3")
    response = await client.put(
        slot["upload"]["url"], content=PNG, headers=slot["upload"]["headers"]
    )
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"


async def test_confirm_without_object_is_409(client, account):
    slot = await upload_slot(client, account[1])
    response = await client.post(confirm_url(slot), headers=account[1])
    assert response.status_code == 409 and response.json()["code"] == "ERR_FILE_004"


@pytest.mark.parametrize("data", [b"<svg>spoofed</svg>", JPEG, b""])
async def test_confirm_rejects_spoofed_content_and_deletes(client, db, account, storage, data):
    slot = await upload_slot(client, account[1])
    grant = decode_upload_token(slot["upload"]["url"].rsplit("/", 1)[1])
    await storage.put(grant.key, data, content_type="image/png")
    response = await client.post(confirm_url(slot), headers=account[1])
    assert response.status_code == 415 and response.json()["code"] == "ERR_FILE_003"
    assert await storage.stat(grant.key) is None
    assert await stored_file(db, slot["file_id"]) is None


async def test_confirm_rejects_oversize_object_and_deletes(client, db, account, storage):
    slot = await upload_slot(client, account[1])
    grant = decode_upload_token(slot["upload"]["url"].rsplit("/", 1)[1])
    await storage.put(grant.key, PNG + bytes(UPLOAD_AVATAR_MAX_BYTES), content_type="image/png")
    response = await client.post(confirm_url(slot), headers=account[1])
    assert response.status_code == 413 and response.json()["code"] == "ERR_FILE_002"
    assert await storage.stat(grant.key) is None
    assert await stored_file(db, slot["file_id"]) is None


async def test_confirm_is_idempotent(client, db, account, storage, monkeypatch):
    file = await ready_upload(client, account[1])
    row = await stored_file(db, file["id"])
    confirmed_at = row.confirmed_at

    async def fail(*args, **kwargs):
        raise AssertionError("Already ready files must not be inspected again")

    monkeypatch.setattr(storage, "stat", fail)
    response = await client.post(f"/api/files/{file['id']}/confirm", headers=account[1])
    assert response.status_code == 200 and response.json() == file
    await db.refresh(row)
    assert row.confirmed_at == confirmed_at


async def test_confirm_by_other_user_is_404(client, account):
    slot = await upload_slot(client, account[1])
    _, other = await register_and_login(client, "other@example.com")
    response = await client.post(confirm_url(slot), headers=other)
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"


async def test_content_public_avatar_needs_no_auth(client, account):
    file = await ready_upload(client, account[1])
    response = await client.get(file["url"])
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_content_pending_file_is_404(client, account):
    slot = await upload_slot(client, account[1])
    response = await client.get(content_url(slot["file_id"]))
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"
    assert (await client.get(content_url(uuid.uuid4()))).status_code == 404


async def test_content_redirects_when_storage_presigns(client, account, storage, monkeypatch):
    file = await ready_upload(client, account[1])

    async def presign(key, *, ttl, filename=None):
        assert ttl == timedelta(seconds=UPLOAD_PRESIGN_TTL_SECONDS)
        return "https://storage.example.com/signed"

    monkeypatch.setattr(storage, "presigned_get", presign)
    response = await client.get(file["url"], follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://storage.example.com/signed"
    assert response.headers["cache-control"] == "private, max-age=60"


@pytest.mark.parametrize("owner", ["user", "organization"])
async def test_content_private_purpose_requires_owner(client, db, account, monkeypatch, owner):
    file = await ready_upload(client, account[1])
    monkeypatch.setitem(
        FILE_RULES,
        FilePurpose.AVATAR,
        replace(FILE_RULES[FilePurpose.AVATAR], public=False, owner=owner),
    )
    if owner == "organization":
        org = await create_org(client, account[1])
        row = await stored_file(db, file["id"])
        row.organization_id = uuid.UUID(org["id"])
        row.user_id = None
        await db.commit()
    _, other = await register_and_login(client, "other@example.com")
    for headers in ({}, other, {"Authorization": "Bearer invalid"}):
        response = await client.get(file["url"], headers=headers)
        assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"
    response = await client.get(file["url"], headers=account[1])
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    "content_type,extension", [("image/png", "png"), ("image/jpeg", "jpg"), ("image/webp", "webp")]
)
async def test_key_is_derived_server_side_and_user_scoped(
    client, db, account, content_type, extension
):
    slot = await upload_slot(
        client,
        account[1],
        content_type=content_type,
        filename="../../evil.svg",
        key="org/attacker/path",
    )
    file = await stored_file(db, slot["file_id"])
    prefix = f"user/{account[0]['id']}/avatars/"
    assert file.key.startswith(prefix) and file.key.endswith(f".{extension}")
    uuid.UUID(file.key.removeprefix(prefix).removesuffix(f".{extension}"))
    assert "evil" not in file.key and "attacker" not in file.key


@pytest.mark.parametrize(
    "operation,stage",
    [
        ("presigned_put", "create"),
        ("stat", "confirm"),
        ("get", "confirm"),
        ("get", "content"),
        ("presigned_get", "content"),
        ("put", "upload"),
        ("delete", "reject"),
    ],
)
async def test_storage_failures_are_catalogued(
    client, account, storage, monkeypatch, operation, stage
):
    slot = await upload_slot(client, account[1])
    grant = decode_upload_token(slot["upload"]["url"].rsplit("/", 1)[1])
    await storage.put(grant.key, b"spoofed" if stage == "reject" else PNG, content_type="image/png")
    if stage == "content":
        assert (await client.post(confirm_url(slot), headers=account[1])).status_code == 200

    async def fail(*args, **kwargs):
        raise StorageError("unavailable")

    monkeypatch.setattr(storage, operation, fail)
    if stage == "create":
        response = await create_upload(client, account[1])
    elif stage == "upload":
        response = await client.put(
            slot["upload"]["url"], content=PNG, headers=slot["upload"]["headers"]
        )
    elif stage == "content":
        response = await client.get(content_url(slot["file_id"]))
    else:
        response = await client.post(confirm_url(slot), headers=account[1])
    assert response.status_code == 503 and response.json()["code"] == "ERR_FILE_005"


@pytest.mark.parametrize(
    "head,expected",
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (WEBP, "image/webp"),
        (b"RIFF", None),
        (b"RIFF1234FAKE", None),
        (b"", None),
    ],
)
def test_sniff_image_type(head, expected):
    assert sniff_image_type(head) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/api/files/{id}/content",
        "/api/files/{id}/content?extra=1",
        "/api/files/{id}/content/",
        "/api/files/not-a-uuid/content",
        "//api/files/{id}/content",
    ],
)
def test_facade_only_parses_own_relative_content_urls(url):
    file_id = uuid.uuid4()
    assert FileService.file_id_from_url(url.format(id=file_id)) is None
    assert FileService.file_id_from_url(content_url(file_id)) == file_id


@pytest.mark.parametrize("has_object", [False, True])
async def test_create_upload_replaces_previous_pending_upload(
    client, db, account, storage, has_object
):
    previous = await upload_slot(client, account[1])
    key = (await stored_file(db, previous["file_id"])).key
    if has_object:
        response = await client.put(
            previous["upload"]["url"], content=PNG, headers=previous["upload"]["headers"]
        )
        assert response.status_code == 204
    current = await upload_slot(client, account[1])
    assert current["file_id"] != previous["file_id"]
    assert await stored_file(db, previous["file_id"]) is None
    assert await storage.stat(key) is None
    assert (await stored_file(db, current["file_id"])).status == "pending"
    response = await client.post(confirm_url(previous), headers=account[1])
    assert response.status_code == 404


async def fill_ready_quota(client, headers):
    return [await ready_upload(client, headers) for _ in range(UPLOAD_AVATAR_MAX_FILES)]


async def test_create_upload_rejects_when_ready_file_quota_reached(client, db, account, storage):
    files = await fill_ready_quota(client, account[1])
    # Legacy rows may already contain an abandoned attempt at the quota. Its
    # cleanup must persist even though the new attempt receives a 429 response.
    user_id = uuid.UUID(account[0]["id"])
    pending = StoredFile(
        key=user_key(user_id, "avatars", f"{uuid.uuid4()}.png"),
        purpose=FilePurpose.AVATAR,
        content_type="image/png",
        user_id=user_id,
        created_by_id=user_id,
    )
    await storage.put(pending.key, PNG, content_type="image/png")
    db.add(pending)
    await db.commit()
    response = await create_upload(client, account[1])
    assert response.status_code == 429, response.text
    assert await stored_file(db, str(pending.id)) is None
    assert await storage.stat(pending.key) is None
    owned = (await db.scalars(select(StoredFile).where(StoredFile.user_id == user_id))).all()
    assert len(owned) == UPLOAD_AVATAR_MAX_FILES
    assert {str(file.id) for file in owned} == {file["id"] for file in files}
    assert all(file.is_ready for file in owned)


async def test_quota_error_is_catalogued_429(client, account):
    await fill_ready_quota(client, account[1])
    response = await create_upload(client, account[1])
    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "ERR_FILE_006"
    assert response.json()["status"] == 429
    assert response.json()["instance"] == response.headers["x-request-id"]


async def test_quota_counts_only_the_callers_files(client, db, account):
    _, other = await register_and_login(client, "quota-other@example.com")
    other_files = await fill_ready_quota(client, other)
    own_files = await fill_ready_quota(client, account[1])
    assert len(own_files) == UPLOAD_AVATAR_MAX_FILES
    for file in other_files:
        assert (await stored_file(db, file["id"])).is_ready
    assert (await create_upload(client, other)).status_code == 429
    assert (await create_upload(client, account[1])).status_code == 429


async def test_concurrent_uploads_preserve_pending_bound(client, db, account):
    responses = await asyncio.gather(
        create_upload(client, account[1]), create_upload(client, account[1])
    )
    assert [response.status_code for response in responses] == [201, 201]
    files = (
        await db.scalars(
            select(StoredFile).where(StoredFile.user_id == uuid.UUID(account[0]["id"]))
        )
    ).all()
    assert len(files) == 1 and not files[0].is_ready
    assert str(files[0].id) in {response.json()["file_id"] for response in responses}
