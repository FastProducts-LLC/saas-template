"""Pending-file worker integration: real transactions and temporary objects."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.policy import UPLOAD_PENDING_TTL_HOURS
from app.core.storage import StorageError, user_key
from app.domains.files import worker
from app.domains.files.domain.entities import FilePurpose, StoredFile
from app.domains.files.interface.deps import build_file_service
from tests.helpers import create_org, register_and_login
from tests.test_files_uploads import PNG
from tests.test_files_uploads import storage as storage


@pytest.fixture
async def sweep(client, db, monkeypatch):
    user, _ = await register_and_login(client)
    monkeypatch.setattr(worker, "SessionLocal", async_sessionmaker(db.bind, expire_on_commit=False))
    return uuid.UUID(user["id"]), worker.sweep_stale_uploads


async def add_file(db, storage, user_id, *, stale=True, ready=False, object_exists=True):
    file = StoredFile(
        key=user_key(user_id, "avatars", f"{uuid.uuid4()}.png"),
        purpose=FilePurpose.AVATAR,
        content_type="image/png",
        user_id=user_id,
        created_by_id=user_id,
        created_at=datetime.now(UTC)
        - timedelta(hours=UPLOAD_PENDING_TTL_HOURS + 1 if stale else 0),
    )
    if ready:
        file.confirm(size_bytes=len(PNG))
    if object_exists:
        await storage.put(file.key, PNG, content_type="image/png")
    db.add(file)
    await db.commit()
    return file


async def exists(db, file):
    return await db.scalar(select(StoredFile.id).where(StoredFile.id == file.id)) is not None


async def test_sweep_deletes_stale_pending_files(db, storage, sweep, caplog):
    user_id, run = sweep
    file = await add_file(db, storage, user_id)
    with caplog.at_level("INFO", logger=worker.__name__):
        assert await run() == 1
    assert not await exists(db, file)
    assert await storage.stat(file.key) is None
    assert "scanned=1 deleted=1 failed=0" in caplog.text


async def test_sweep_keeps_recent_pending_and_ready_files(db, storage, sweep):
    user_id, run = sweep
    recent = await add_file(db, storage, user_id, stale=False)
    ready = await add_file(db, storage, user_id, ready=True)
    assert await run() == 0
    for file in (recent, ready):
        assert await exists(db, file)
        assert await storage.get(file.key) == PNG


async def test_sweep_tolerates_missing_object(db, storage, sweep):
    user_id, run = sweep
    file = await add_file(db, storage, user_id, object_exists=False)
    assert await run() == 1
    assert not await exists(db, file)


async def test_sweep_is_idempotent(db, storage, sweep):
    user_id, run = sweep
    file = await add_file(db, storage, user_id)
    assert await run() == 1
    assert await run() == 0
    assert not await exists(db, file)
    assert await storage.stat(file.key) is None


async def test_sweep_continues_after_failure_and_retries(db, storage, sweep, monkeypatch):
    user_id, run = sweep
    failed = await add_file(db, storage, user_id)
    successful = await add_file(db, storage, user_id)
    delete = storage.delete

    async def fail_one(key):
        if key == failed.key:
            raise StorageError("unavailable")
        await delete(key)

    monkeypatch.setattr(storage, "delete", fail_one)
    assert await run() == 1
    assert await exists(db, failed) and not await exists(db, successful)
    assert await storage.stat(failed.key) is not None
    monkeypatch.setattr(storage, "delete", delete)
    assert await run() == 1
    assert not await exists(db, failed)


async def test_sweep_bounds_each_batch(db, storage, sweep, monkeypatch):
    user_id, run = sweep
    monkeypatch.setattr(worker, "SWEEP_BATCH_SIZE", 1)
    files = [await add_file(db, storage, user_id) for _ in range(2)]
    assert await run() == 1
    assert sum([await exists(db, file) for file in files]) == 1
    assert await run() == 1


async def test_facade_deletes_only_requested_owners_files(client, db, storage):
    user, headers = await register_and_login(client)
    other, _ = await register_and_login(client, "other@example.com")
    first = await add_file(db, storage, uuid.UUID(user["id"]), ready=True)
    second = await add_file(db, storage, uuid.UUID(other["id"]), ready=True)
    org = await create_org(client, headers)
    org_file = await add_file(db, storage, uuid.UUID(user["id"]))
    org_file.organization_id = uuid.UUID(org["id"])
    org_file.user_id = None
    await db.commit()
    service = build_file_service(db)
    assert await service.delete_all_for_user(uuid.UUID(user["id"])) == 1
    await db.commit()
    assert not await exists(db, first) and await exists(db, second) and await exists(db, org_file)
    assert await service.delete_all_for_org(uuid.UUID(org["id"])) == 1
    await db.commit()
    assert not await exists(db, org_file) and await exists(db, second)
    assert await storage.stat(first.key) is None and await storage.stat(org_file.key) is None
    assert await storage.stat(second.key) is not None
    await service.delete_file(first.id)  # Idempotent on missing metadata.
    assert await service.delete_all_for_user(uuid.UUID(user["id"])) == 0


async def test_facade_deletion_is_best_effort_on_storage(client, db, storage, monkeypatch):
    user, _ = await register_and_login(client)
    file = await add_file(db, storage, uuid.UUID(user["id"]), ready=True)

    async def fail(key):
        raise StorageError("unavailable")

    monkeypatch.setattr(storage, "delete", fail)
    await build_file_service(db).delete_file(file.id)
    await db.commit()
    assert not await exists(db, file)
