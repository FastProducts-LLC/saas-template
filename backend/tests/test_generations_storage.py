"""Generation file routes use configured storage, preserving tenancy and old keys."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.policy import UPLOAD_PRESIGN_TTL_SECONDS
from app.core.storage import LocalFileStorage, get_file_storage, org_key
from app.core.storage.base import StorageError
from app.core.storage.factory import reset_file_storage_cache
from app.domains.credits.domain import CreditAction
from app.domains.generations import worker
from app.domains.generations.domain import GeneratedAsset, Generation, GenerationStatus
from app.domains.generations.infrastructure.media_store import StorageMediaStore
from app.domains.generations.infrastructure.providers import DispatchingProviderGateway
from app.main import app
from tests.helpers import create_org, register_and_login

DATA = b"generated image bytes"
SIGNED_URL = "https://objects.example.test/result.png?signature=test"


@pytest.fixture(autouse=True)
def storage(monkeypatch, tmp_path):
    reset_file_storage_cache()
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    yield get_file_storage()
    reset_file_storage_cache()


async def _generation(client, db, storage, *, legacy=False, pending=False):
    user, headers = await register_and_login(client)
    org = await create_org(client, headers)
    generation = Generation(
        organization_id=uuid.UUID(org["id"]),
        user_id=uuid.UUID(user["id"]),
        kind=CreditAction.IMAGE_NANO_BANANA,
        model="test-model",
        prompt="a cat",
    )
    if not pending:
        name = f"{generation.id}.png"
        if legacy:
            key = f"{generation.organization_id}/{name}"
            await storage.put(key, DATA, content_type="image/png")
        else:
            key = await StorageMediaStore(storage).save(
                generation.organization_id, name, GeneratedAsset(DATA, "image/png")
            )
        generation.succeed(key, "image/png")
    db.add(generation)
    await db.commit()
    return generation, headers


def _url(generation, *, org_id=None):
    org_id = org_id or generation.organization_id
    return f"/api/orgs/{org_id}/generations/{generation.id}/file"


class PresigningStorage(LocalFileStorage):
    signed_key = None

    async def presigned_get(self, key, *, ttl, filename=None):
        assert ttl == timedelta(seconds=UPLOAD_PRESIGN_TTL_SECONDS)
        self.signed_key = key
        return SIGNED_URL


async def test_download_streams_bytes_with_local_storage(client, db, storage):
    generation, headers = await _generation(client, db, storage)
    response = await client.get(_url(generation), headers=headers)
    assert response.status_code == 200, response.text
    assert response.content == DATA
    assert response.headers["content-type"] == "image/png"


async def test_download_streams_bytes_even_when_storage_presigns(
    client,
    db,
    storage,
    monkeypatch,
    tmp_path,
):
    generation, headers = await _generation(client, db, storage)
    presigning = PresigningStorage(tmp_path)
    monkeypatch.setitem(app.dependency_overrides, get_file_storage, lambda: presigning)
    response = await client.get(_url(generation), headers=headers, follow_redirects=False)
    assert response.status_code == 200, response.text
    assert response.content == DATA
    assert response.headers["content-type"] == "image/png"
    assert "location" not in response.headers
    assert presigning.signed_key is None


async def test_file_url_returns_presigned_url_when_storage_presigns(
    client,
    db,
    storage,
    monkeypatch,
    tmp_path,
):
    generation, headers = await _generation(client, db, storage)
    presigning = PresigningStorage(tmp_path)
    monkeypatch.setitem(app.dependency_overrides, get_file_storage, lambda: presigning)
    response = await client.get(_url(generation) + "-url", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"url": SIGNED_URL, "expires_in": UPLOAD_PRESIGN_TTL_SECONDS}
    assert response.headers["cache-control"] == "no-store"
    assert presigning.signed_key == generation.file_path


async def test_file_url_is_null_for_local_storage(client, db, storage):
    generation, headers = await _generation(client, db, storage)
    response = await client.get(_url(generation) + "-url", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"url": None, "expires_in": None}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("presigns", [False, True])
@pytest.mark.parametrize("suffix", ["", "-url"])
async def test_download_missing_object_is_404(
    client,
    db,
    storage,
    monkeypatch,
    tmp_path,
    presigns,
    suffix,
):
    generation, headers = await _generation(client, db, storage)
    await storage.delete(generation.file_path)
    if presigns:
        monkeypatch.setitem(
            app.dependency_overrides, get_file_storage, lambda: PresigningStorage(tmp_path)
        )
    response = await client.get(_url(generation) + suffix, headers=headers, follow_redirects=False)
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "ERR_GEN_001"


async def test_download_other_org_is_404(client, db, storage):
    generation, headers = await _generation(client, db, storage)
    other_org = await create_org(client, headers, name="Other organization")
    # This user belongs to both orgs, so this exercises the generation's tenant filter.
    response = await client.get(_url(generation, org_id=other_org["id"]), headers=headers)
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "ERR_GEN_001"


async def test_file_url_other_org_is_404(client, db, storage):
    generation, headers = await _generation(client, db, storage)
    other_org = await create_org(client, headers, name="Other organization")
    response = await client.get(_url(generation, org_id=other_org["id"]) + "-url", headers=headers)
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "ERR_GEN_001"


async def test_file_url_without_result_is_not_ready(client, db, storage):
    generation, headers = await _generation(client, db, storage, pending=True)
    response = await client.get(_url(generation) + "-url", headers=headers)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "ERR_GEN_004"


async def test_new_asset_key_is_org_scoped(client, db, storage, monkeypatch):
    generation, headers = await _generation(client, db, storage, pending=True)
    monkeypatch.setattr(worker, "SessionLocal", async_sessionmaker(db.bind, expire_on_commit=False))

    async def generate(self, kind, prompt):
        return GeneratedAsset(DATA, "image/png")

    monkeypatch.setattr(DispatchingProviderGateway, "run", generate)
    await worker.execute_generation(generation.id)
    await db.refresh(generation)
    expected = org_key(generation.organization_id, "generations", f"{generation.id}.png")
    assert generation.status == GenerationStatus.SUCCEEDED
    assert generation.file_path == expected
    assert len(expected) <= 255
    assert await storage.get(expected) == DATA
    response = await client.get(_url(generation), headers=headers)
    assert response.status_code == 200, response.text
    assert response.content == DATA


async def test_legacy_file_path_still_downloads(client, db, storage):
    generation, headers = await _generation(client, db, storage, legacy=True)
    assert generation.file_path == f"{generation.organization_id}/{generation.id}.png"
    response = await client.get(_url(generation), headers=headers)
    assert response.status_code == 200, response.text
    assert response.content == DATA


@pytest.mark.parametrize("legacy", [False, True])
async def test_delete_generation_removes_object(client, db, storage, legacy):
    generation, headers = await _generation(client, db, storage, legacy=legacy)
    key = generation.file_path
    response = await client.delete(_url(generation).removesuffix("/file"), headers=headers)
    assert response.status_code == 204, response.text
    assert await storage.stat(key) is None
    response = await client.get(_url(generation), headers=headers)
    assert response.status_code == 404


async def test_storage_failure_on_download_is_catalogued_error(
    client,
    db,
    storage,
    monkeypatch,
):
    generation, headers = await _generation(client, db, storage)

    async def fail(*args, **kwargs):
        raise StorageError("Storage unavailable")

    monkeypatch.setattr(storage, "get", fail)
    response = await client.get(_url(generation), headers=headers)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "ERR_FILE_005"
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize("operation", ["stat", "presigned_get"])
async def test_storage_failure_on_file_url_is_catalogued_error(
    client, db, storage, monkeypatch, operation
):
    generation, headers = await _generation(client, db, storage)

    async def fail(*args, **kwargs):
        raise StorageError("Storage unavailable")

    monkeypatch.setattr(storage, operation, fail)
    response = await client.get(_url(generation) + "-url", headers=headers)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "ERR_FILE_005"
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_storage_failure_does_not_prevent_delete(client, db, storage, monkeypatch, caplog):
    generation, headers = await _generation(client, db, storage)

    async def fail(key):
        raise StorageError(SIGNED_URL)

    monkeypatch.setattr(storage, "delete", fail)
    response = await client.delete(_url(generation).removesuffix("/file"), headers=headers)
    assert response.status_code == 204, response.text
    assert "StorageError" in caplog.text
    assert SIGNED_URL not in caplog.text
    response = await client.get(_url(generation), headers=headers)
    assert response.status_code == 404
