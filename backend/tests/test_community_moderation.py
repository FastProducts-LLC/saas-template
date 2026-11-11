"""API tests for superuser community moderation: ban/unban, hide/unhide,
and the admin member list."""

from tests.helpers import make_superuser, register_and_login


async def _superuser(client, db, email="mod-admin@example.com"):
    user, headers = await register_and_login(client, email)
    await make_superuser(db, user["id"])
    return headers


async def _enable_and_join(client, db, admin_headers):
    res = await client.put(
        "/api/admin/flags/community", json={"enabled": True}, headers=admin_headers
    )
    assert res.status_code == 200
    user, headers = await register_and_login(client, "moderated@example.com")
    res = await client.post(
        "/api/community/profile",
        json={"handle": "moderated", "display_name": "Moderated", "bio": None},
        headers=headers,
    )
    assert res.status_code == 201
    return user, headers


async def test_moderation_requires_superuser(client, db):
    admin_headers = await _superuser(client, db)
    user, user_headers = await _enable_and_join(client, db, admin_headers)

    res = await client.get("/api/admin/community/members", headers=user_headers)
    assert res.status_code == 403
    res = await client.post(f"/api/admin/community/members/{user['id']}/ban", headers=user_headers)
    assert res.status_code == 403


async def test_admin_list_includes_hidden_and_banned(client, db):
    admin_headers = await _superuser(client, db)
    user, _ = await _enable_and_join(client, db, admin_headers)

    assert (
        await client.post(
            f"/api/admin/community/members/{user['id']}/hide-profile",
            headers=admin_headers,
        )
    ).status_code == 204

    page = (await client.get("/api/admin/community/members", headers=admin_headers)).json()
    row = next(r for r in page["items"] if r["handle"] == "moderated")
    assert row["is_hidden"] is True
    assert row["email"] == "moderated@example.com"

    # Hidden profile is gone from the member-facing directory...
    _, viewer = await register_and_login(client, "viewer-mod@example.com")
    directory = (await client.get("/api/community/members", headers=viewer)).json()
    assert all(m["handle"] != "moderated" for m in directory["items"])

    # ...and comes back after unhide.
    assert (
        await client.post(
            f"/api/admin/community/members/{user['id']}/unhide-profile",
            headers=admin_headers,
        )
    ).status_code == 204
    directory = (await client.get("/api/community/members", headers=viewer)).json()
    assert any(m["handle"] == "moderated" for m in directory["items"])


async def test_ban_locks_out_and_unban_restores(client, db):
    admin_headers = await _superuser(client, db)
    user, user_headers = await _enable_and_join(client, db, admin_headers)

    assert (
        await client.post(f"/api/admin/community/members/{user['id']}/ban", headers=admin_headers)
    ).status_code == 204

    # Banned member is rejected from community actions...
    res = await client.patch("/api/community/profile", json={"bio": "hi"}, headers=user_headers)
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_COMM_005"
    res = await client.get("/api/community/conversations", headers=user_headers)
    assert res.status_code == 403

    # ...and invisible in the directory.
    _, viewer = await register_and_login(client, "viewer-ban@example.com")
    directory = (await client.get("/api/community/members", headers=viewer)).json()
    assert all(m["handle"] != "moderated" for m in directory["items"])

    assert (
        await client.post(f"/api/admin/community/members/{user['id']}/unban", headers=admin_headers)
    ).status_code == 204
    res = await client.patch("/api/community/profile", json={"bio": "back"}, headers=user_headers)
    assert res.status_code == 200


async def test_ban_unknown_member_404(client, db):
    admin_headers = await _superuser(client, db)
    import uuid

    res = await client.post(
        f"/api/admin/community/members/{uuid.uuid4()}/ban", headers=admin_headers
    )
    assert res.status_code == 404


async def test_admin_routes_work_with_flag_off(client, db):
    """Moderation is deliberately NOT behind the feature flag."""
    admin_headers = await _superuser(client, db)
    user, _ = await _enable_and_join(client, db, admin_headers)
    res = await client.put(
        "/api/admin/flags/community", json={"enabled": False}, headers=admin_headers
    )
    assert res.status_code == 200

    page = await client.get("/api/admin/community/members", headers=admin_headers)
    assert page.status_code == 200
    assert any(r["handle"] == "moderated" for r in page.json()["items"])
