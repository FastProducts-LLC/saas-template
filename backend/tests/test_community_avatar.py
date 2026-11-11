"""Community avatar lifecycle through the files facade and real HTTP routes."""

import uuid

import pytest

from app.domains.community.domain.entities import CommunityMembership
from tests.helpers import register_and_login
from tests.test_community_profiles import JOIN_BODY, enable_community
from tests.test_files_uploads import (
    PNG,
    create_upload,
    fill_ready_quota,
    ready_upload,
    stored_file,
    upload_slot,
)
from tests.test_files_uploads import storage as storage

AVATAR = "/api/community/profile/avatar"
PROFILE = "/api/community/profile"


@pytest.fixture
async def member(client, db):
    await enable_community(client, db)
    user, headers = await register_and_login(client, "avatar-member@example.com")
    response = await client.post(PROFILE, json=JOIN_BODY, headers=headers)
    assert response.status_code == 201, response.text
    return user, headers


async def set_avatar(client, headers, file):
    return await client.put(AVATAR, json={"file_id": file["id"]}, headers=headers)


async def test_set_avatar_from_uploaded_file(client, member):
    file = await ready_upload(client, member[1])
    response = await set_avatar(client, member[1], file)
    assert response.status_code == 200, response.text
    assert response.json()["avatar_url"] == file["url"]
    assert response.json()["handle"] == JOIN_BODY["handle"]
    me = await client.get("/api/community/me", headers=member[1])
    assert me.json()["profile"]["avatar_url"] == file["url"]
    # Assigning the same file again must not delete it.
    assert (await set_avatar(client, member[1], file)).status_code == 200
    assert (await client.get(file["url"])).status_code == 200


async def test_set_avatar_rejects_other_users_file(client, member):
    _, other = await register_and_login(client, "other-avatar@example.com")
    file = await ready_upload(client, other)
    response = await set_avatar(client, member[1], file)
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"
    assert (await client.get(file["url"])).status_code == 200


async def test_set_avatar_rejects_pending_file(client, member):
    slot = await upload_slot(client, member[1])
    response = await set_avatar(client, member[1], {"id": slot["file_id"]})
    assert response.status_code == 404 and response.json()["code"] == "ERR_FILE_001"


async def test_replacing_avatar_deletes_previous_file(client, db, storage, member):
    first = await ready_upload(client, member[1])
    assert (await set_avatar(client, member[1], first)).status_code == 200
    key = (await stored_file(db, first["id"])).key
    second = await ready_upload(client, member[1])
    response = await set_avatar(client, member[1], second)
    assert response.status_code == 200 and response.json()["avatar_url"] == second["url"]
    assert await storage.stat(key) is None
    assert await stored_file(db, first["id"]) is None
    assert (await client.get(second["url"])).status_code == 200


async def test_delete_avatar_clears_url_and_deletes_file(client, db, storage, member):
    file = await ready_upload(client, member[1])
    assert (await set_avatar(client, member[1], file)).status_code == 200
    key = (await stored_file(db, file["id"])).key
    response = await client.delete(AVATAR, headers=member[1])
    assert response.status_code == 204 and response.content == b""
    me = await client.get("/api/community/me", headers=member[1])
    assert me.json()["profile"]["avatar_url"] is None
    assert await storage.stat(key) is None
    assert await stored_file(db, file["id"]) is None


async def test_delete_avatar_without_avatar_is_204(client, member):
    for _ in range(2):
        response = await client.delete(AVATAR, headers=member[1])
        assert response.status_code == 204 and response.content == b""


async def test_patch_profile_with_external_url_still_works(client, db, storage, member):
    file = await ready_upload(client, member[1])
    assert (await set_avatar(client, member[1], file)).status_code == 200
    key = (await stored_file(db, file["id"])).key
    response = await client.patch(
        PROFILE, json={"avatar_url": "https://example.com/avatar.png"}, headers=member[1]
    )
    assert response.status_code == 200
    assert response.json()["avatar_url"] == "https://example.com/avatar.png"
    assert await stored_file(db, file["id"]) is None
    assert await storage.stat(key) is None
    assert (await client.delete(AVATAR, headers=member[1])).status_code == 204


@pytest.mark.parametrize("value", [None, ""])
async def test_patch_clearing_uploaded_avatar_deletes_file(client, db, storage, member, value):
    file = await ready_upload(client, member[1])
    assert (await set_avatar(client, member[1], file)).status_code == 200
    key = (await stored_file(db, file["id"])).key
    # An unrelated partial edit must preserve the upload.
    response = await client.patch(PROFILE, json={"bio": "Updated"}, headers=member[1])
    assert response.status_code == 200 and response.json()["avatar_url"] == file["url"]
    assert (await client.get(file["url"])).status_code == 200
    response = await client.patch(PROFILE, json={"avatar_url": value}, headers=member[1])
    assert response.status_code == 200 and response.json()["avatar_url"] is None
    assert await stored_file(db, file["id"]) is None
    assert await storage.stat(key) is None


async def test_avatar_endpoints_respect_community_flag(client):
    _, headers = await register_and_login(client)
    # Files themselves remain available with community disabled.
    file = await ready_upload(client, headers)
    response = await set_avatar(client, headers, file)
    assert response.status_code == 404 and response.json()["code"] == "ERR_FLAG_002"
    response = await client.delete(AVATAR, headers=headers)
    assert response.status_code == 404 and response.json()["code"] == "ERR_FLAG_002"


@pytest.mark.parametrize("state", ["anonymous", "unverified", "not_joined", "banned"])
async def test_avatar_endpoints_share_profile_access_rules(client, db, member, state):
    file = await ready_upload(client, member[1])
    headers = member[1]
    if state == "anonymous":
        headers, expected = {}, 401
    elif state == "unverified":
        _, headers = await register_and_login(
            client, "unverified-avatar@example.com", verified=False
        )
        expected = 403
    elif state == "not_joined":
        _, headers = await register_and_login(client, "not-joined-avatar@example.com")
        expected = 403
    else:
        from sqlalchemy import select

        membership = await db.scalar(
            select(CommunityMembership).where(
                CommunityMembership.user_id == uuid.UUID(member[0]["id"])
            )
        )
        membership.ban(by=uuid.UUID(member[0]["id"]))
        await db.commit()
        expected = 403
    for response in (
        await set_avatar(client, headers, file),
        await client.delete(AVATAR, headers=headers),
    ):
        assert response.status_code == expected, response.text
    assert (await client.get(file["url"])).status_code == 200


async def avatar_inventory(client, db, headers):
    """Confirmed candidates plus a pending object, all of which need cleanup."""
    files = [await ready_upload(client, headers) for _ in range(3)]
    pending = await upload_slot(client, headers)
    response = await client.put(
        pending["upload"]["url"], content=PNG, headers=pending["upload"]["headers"]
    )
    assert response.status_code == 204
    files.append({"id": pending["file_id"]})
    return [(file, (await stored_file(db, file["id"])).key) for file in files]


async def test_set_avatar_deletes_users_other_avatar_files(client, db, storage, member):
    files = await avatar_inventory(client, db, member[1])
    chosen = files[0][0]
    response = await set_avatar(client, member[1], chosen)
    assert response.status_code == 200 and response.json()["avatar_url"] == chosen["url"]
    for file, key in files:
        if file["id"] == chosen["id"]:
            assert (await stored_file(db, file["id"])).is_ready
            assert await storage.get(key) == PNG
        else:
            assert await stored_file(db, file["id"]) is None
            assert await storage.stat(key) is None


@pytest.mark.parametrize("has_avatar", [False, True])
async def test_delete_avatar_deletes_all_users_avatar_files(
    client, db, storage, member, has_avatar
):
    current = None
    if has_avatar:
        current = await ready_upload(client, member[1])
        assert (await set_avatar(client, member[1], current)).status_code == 200
    files = await avatar_inventory(client, db, member[1])
    if current:
        files.append((current, (await stored_file(db, current["id"])).key))
    response = await client.delete(AVATAR, headers=member[1])
    assert response.status_code == 204
    for file, key in files:
        assert await stored_file(db, file["id"]) is None
        assert await storage.stat(key) is None
    me = await client.get("/api/community/me", headers=member[1])
    assert me.json()["profile"]["avatar_url"] is None


async def test_patch_without_avatar_field_deletes_nothing(client, db, storage, member):
    current = await ready_upload(client, member[1])
    assert (await set_avatar(client, member[1], current)).status_code == 200
    files = await avatar_inventory(client, db, member[1])
    files.append((current, (await stored_file(db, current["id"])).key))
    response = await client.patch(PROFILE, json={"bio": "Only a bio edit"}, headers=member[1])
    assert response.status_code == 200 and response.json()["avatar_url"] == current["url"]
    for file, key in files:
        assert await stored_file(db, file["id"]) is not None
        assert await storage.get(key) == PNG


@pytest.mark.parametrize("change", ["set", "delete", "patch_clear", "patch_external"])
async def test_avatar_change_never_deletes_another_users_files(client, db, storage, member, change):
    _, other = await register_and_login(client, "other-inventory@example.com")
    other_files = await avatar_inventory(client, db, other)
    current = await ready_upload(client, member[1])
    assert (await set_avatar(client, member[1], current)).status_code == 200
    abandoned = await avatar_inventory(client, db, member[1])
    current_key = (await stored_file(db, current["id"])).key
    if change == "set":
        response = await set_avatar(client, member[1], current)
        assert response.status_code == 200
    elif change == "delete":
        response = await client.delete(AVATAR, headers=member[1])
        assert response.status_code == 204
    else:
        url = None if change == "patch_clear" else "https://example.com/external.png"
        response = await client.patch(PROFILE, json={"avatar_url": url}, headers=member[1])
        assert response.status_code == 200
    for file, key in abandoned:
        assert await stored_file(db, file["id"]) is None
        assert await storage.stat(key) is None
    if change != "set":
        assert await stored_file(db, current["id"]) is None
        assert await storage.stat(current_key) is None
    for file, key in other_files:
        assert await stored_file(db, file["id"]) is not None
        assert await storage.get(key) == PNG


@pytest.mark.parametrize("change", ["set", "delete", "patch_clear"])
async def test_avatar_change_recovers_from_upload_quota(client, member, change):
    files = await fill_ready_quota(client, member[1])
    assert (await create_upload(client, member[1])).status_code == 429
    if change == "set":
        assert (await set_avatar(client, member[1], files[0])).status_code == 200
    elif change == "delete":
        assert (await client.delete(AVATAR, headers=member[1])).status_code == 204
    else:
        response = await client.patch(PROFILE, json={"avatar_url": None}, headers=member[1])
        assert response.status_code == 200
    assert (await create_upload(client, member[1])).status_code == 201
