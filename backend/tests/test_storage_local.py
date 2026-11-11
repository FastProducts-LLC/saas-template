"""Local storage and upload-grant contract tests."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.storage.base import StorageError, StorageObjectNotFound
from app.core.storage.local import LocalFileStorage, decode_upload_token

TTL = timedelta(minutes=5)
KEY = "org/test/generations/result.png"


@pytest.fixture
def storage(tmp_path):
    return LocalFileStorage(tmp_path)


async def test_put_get_roundtrip(storage, tmp_path):
    await storage.put(KEY, b"first", content_type="image/png")
    await storage.put(KEY, b"replacement", content_type="image/png")
    assert await storage.get(KEY) == b"replacement"
    assert (tmp_path / KEY).read_bytes() == b"replacement"
    assert list((tmp_path / KEY).parent.iterdir()) == [tmp_path / KEY]


async def test_get_missing_raises_not_found(storage):
    with pytest.raises(StorageObjectNotFound):
        await storage.get(KEY)


async def test_delete_is_idempotent(storage):
    await storage.put(KEY, b"data", content_type="image/png")
    await storage.delete(KEY)
    await storage.delete(KEY)
    assert await storage.stat(KEY) is None


async def test_stat_reports_size_and_none_when_missing(storage):
    assert await storage.stat(KEY) is None
    await storage.put(KEY, b"data", content_type="image/png")
    info = await storage.stat(KEY)
    assert (info.key, info.size_bytes, info.content_type) == (KEY, 4, "image/png")


async def test_presigned_get_is_none(storage):
    assert await storage.presigned_get(KEY, ttl=TTL) is None


async def test_presigned_put_token_roundtrip(storage):
    before = datetime.now(UTC)
    upload = await storage.presigned_put(KEY, content_type="image/png", max_bytes=123, ttl=TTL)
    assert upload.url.startswith("/api/files/local-upload/")
    assert upload.method == "PUT"
    assert upload.headers == {"Content-Type": "image/png"}
    grant = decode_upload_token(upload.url.rsplit("/", 1)[1])
    assert (grant.key, grant.content_type, grant.max_bytes) == (KEY, "image/png", 123)
    assert grant.expires_at == upload.expires_at
    assert before + TTL - timedelta(seconds=1) <= grant.expires_at <= datetime.now(UTC) + TTL


async def test_upload_token_rejects_tampering(storage):
    upload = await storage.presigned_put(KEY, content_type="image/png", max_bytes=123, ttl=TTL)
    token = upload.url.rsplit("/", 1)[1]
    header, payload, signature = token.split(".")
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(StorageError):
        decode_upload_token(f"{header}.{payload}.{signature}")


async def test_upload_token_rejects_expired(storage):
    upload = await storage.presigned_put(
        KEY, content_type="image/png", max_bytes=123, ttl=timedelta(seconds=-10)
    )
    with pytest.raises(StorageError):
        decode_upload_token(upload.url.rsplit("/", 1)[1])


async def test_upload_token_rejects_other_jwt_types(storage):
    upload = await storage.presigned_put(KEY, content_type="image/png", max_bytes=123, ttl=TTL)
    payload = jwt.decode(
        upload.url.rsplit("/", 1)[1],
        settings.secret_key,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    del payload["purpose"]
    other_token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    with pytest.raises(StorageError):
        decode_upload_token(other_token)


@pytest.mark.parametrize(
    "operation", ["put", "get", "delete", "stat", "presigned_get", "presigned_put"]
)
@pytest.mark.parametrize("key", ["../escape", "/absolute", "org/../escape", "org\\escape"])
async def test_rejects_traversal_key(storage, operation, key):
    kwargs = {}
    args = [key]
    if operation == "put":
        args.append(b"data")
        kwargs["content_type"] = "image/png"
    if operation.startswith("presigned_"):
        kwargs["ttl"] = TTL
    if operation == "presigned_put":
        kwargs.update(content_type="image/png", max_bytes=123)
    with pytest.raises(ValueError):
        await getattr(storage, operation)(*args, **kwargs)


async def test_rejects_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    storage = LocalFileStorage(root)
    with pytest.raises(ValueError):
        await storage.put("link/escape", b"data", content_type="image/png")
    assert not (outside / "escape").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_bytes", True),
        ("max_bytes", -1),
        ("key", 12),
        ("key", "../escape"),
        ("content_type", None),
        ("purpose", "password-reset"),
        ("exp", "9999999999"),
    ],
)
async def test_upload_token_rejects_malformed_payload(storage, field, value):
    upload = await storage.presigned_put(KEY, content_type="image/png", max_bytes=123, ttl=TTL)
    payload = jwt.decode(
        upload.url.rsplit("/", 1)[1],
        settings.secret_key,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    payload[field] = value
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    with pytest.raises(StorageError):
        decode_upload_token(token)
