"""API tests for community DMs: paywall, pair-uniqueness, unread counts,
read receipts, and pagination."""

import uuid

from sqlalchemy import select

from app.domains.community.domain import CommunityMembership, SubscriptionStatus
from tests.helpers import make_superuser, register_and_login


async def _enable_community(client, db):
    user, headers = await register_and_login(client, "msg-admin@example.com")
    await make_superuser(db, user["id"])
    res = await client.put("/api/admin/flags/community", json={"enabled": True}, headers=headers)
    assert res.status_code == 200


async def _join(client, headers, handle: str):
    res = await client.post(
        "/api/community/profile",
        json={"handle": handle, "display_name": handle.title()},
        headers=headers,
    )
    assert res.status_code == 201, res.text


async def _make_premium(db, user_id: str) -> None:
    """Flip the membership row directly — no Stripe in tests."""
    membership = (
        await db.execute(
            select(CommunityMembership).where(CommunityMembership.user_id == uuid.UUID(user_id))
        )
    ).scalar_one()
    membership.apply_subscription(
        subscription_id=f"sub_test_{user_id[:8]}",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=None,
        cancel_at_period_end=False,
        customer_id="cus_test",
    )
    await db.commit()


async def _setup_pair(client, db):
    """Premium alice + free bob, both joined."""
    await _enable_community(client, db)
    alice, alice_h = await register_and_login(client, "alice@example.com")
    bob, bob_h = await register_and_login(client, "bob@example.com")
    await _join(client, alice_h, "alice")
    await _join(client, bob_h, "bob")
    await _make_premium(db, alice["id"])
    return alice_h, bob_h


async def test_free_member_cannot_start_conversation(client, db):
    await _enable_community(client, db)
    _, headers = await register_and_login(client, "freeloader@example.com")
    await _join(client, headers, "freeloader")
    _, other_h = await register_and_login(client, "target@example.com")
    await _join(client, other_h, "target")

    res = await client.post(
        "/api/community/conversations",
        json={"recipient_handle": "target"},
        headers=headers,
    )
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_COMM_004"


async def test_dm_flow_send_read_unread_reply_gate(client, db):
    alice_h, bob_h = await _setup_pair(client, db)

    conv = (
        await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
    ).json()
    assert conv["other"]["handle"] == "bob"

    for body in ("hey bob", "you around?"):
        res = await client.post(
            f"/api/community/conversations/{conv['id']}/messages",
            json={"body": body},
            headers=alice_h,
        )
        assert res.status_code == 201, res.text
        assert res.json()["mine"] is True

    # Bob (free) sees the conversation with an unread count and can read it.
    bob_list = (await client.get("/api/community/conversations", headers=bob_h)).json()
    assert len(bob_list) == 1
    assert bob_list[0]["unread_count"] == 2
    assert bob_list[0]["last_message_preview"] == "you around?"
    assert bob_list[0]["other"]["handle"] == "alice"

    messages = (
        await client.get(f"/api/community/conversations/{conv['id']}/messages", headers=bob_h)
    ).json()
    assert [m["body"] for m in messages["items"]] == ["you around?", "hey bob"]
    assert all(m["mine"] is False for m in messages["items"])

    # But he can't reply without premium.
    res = await client.post(
        f"/api/community/conversations/{conv['id']}/messages",
        json={"body": "hi!"},
        headers=bob_h,
    )
    assert res.status_code == 403
    assert res.json()["code"] == "ERR_COMM_004"

    # Mark read clears the unread count.
    assert (
        await client.post(f"/api/community/conversations/{conv['id']}/read", headers=bob_h)
    ).status_code == 204
    bob_list = (await client.get("/api/community/conversations", headers=bob_h)).json()
    assert bob_list[0]["unread_count"] == 0

    # Alice never counts her own messages as unread.
    alice_list = (await client.get("/api/community/conversations", headers=alice_h)).json()
    assert alice_list[0]["unread_count"] == 0


async def test_starting_twice_returns_same_conversation(client, db):
    alice_h, _ = await _setup_pair(client, db)
    first = (
        await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
    ).json()
    second = (
        await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
    ).json()
    assert first["id"] == second["id"]


async def test_cannot_message_self_or_unavailable_members(client, db):
    alice_h, bob_h = await _setup_pair(client, db)

    res = await client.post(
        "/api/community/conversations",
        json={"recipient_handle": "alice"},
        headers=alice_h,
    )
    assert res.status_code == 400
    assert res.json()["code"] == "ERR_COMM_007"

    res = await client.post(
        "/api/community/conversations",
        json={"recipient_handle": "nobody_here"},
        headers=alice_h,
    )
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_COMM_008"


async def test_non_participant_cannot_access_conversation(client, db):
    alice_h, _ = await _setup_pair(client, db)
    conv = (
        await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
    ).json()

    _, eve_h = await register_and_login(client, "eve@example.com")
    await _join(client, eve_h, "eve")

    res = await client.get(f"/api/community/conversations/{conv['id']}/messages", headers=eve_h)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_COMM_006"

    res = await client.post(f"/api/community/conversations/{conv['id']}/read", headers=eve_h)
    assert res.status_code == 404


async def test_keyset_pagination_newest_first(client, db):
    alice_h, _ = await _setup_pair(client, db)
    conv = (
        await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
    ).json()
    for i in range(1, 6):
        await client.post(
            f"/api/community/conversations/{conv['id']}/messages",
            json={"body": f"msg {i}"},
            headers=alice_h,
        )

    page1 = (
        await client.get(
            f"/api/community/conversations/{conv['id']}/messages?page_size=2",
            headers=alice_h,
        )
    ).json()
    assert [m["body"] for m in page1["items"]] == ["msg 5", "msg 4"]
    assert page1["next_before"] == page1["items"][-1]["id"]

    page2 = (
        await client.get(
            f"/api/community/conversations/{conv['id']}/messages"
            f"?page_size=2&before={page1['next_before']}",
            headers=alice_h,
        )
    ).json()
    assert [m["body"] for m in page2["items"]] == ["msg 3", "msg 2"]

    page3 = (
        await client.get(
            f"/api/community/conversations/{conv['id']}/messages"
            f"?page_size=2&before={page2['next_before']}",
            headers=alice_h,
        )
    ).json()
    assert [m["body"] for m in page3["items"]] == ["msg 1"]
    assert page3["next_before"] is None


async def test_blank_message_rejected(client, db):
    alice_h, _ = await _setup_pair(client, db)
    conv = (
        await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
    ).json()
    res = await client.post(
        f"/api/community/conversations/{conv['id']}/messages",
        json={"body": "   "},
        headers=alice_h,
    )
    assert res.status_code == 422


async def test_rate_limited_send_routes_work_with_limiter_enabled(client, db):
    # Regression: rate-limited POST routes 500'd on the live server — slowapi
    # (headers_enabled=True) requires a `response: Response` param on decorated
    # routes to inject X-RateLimit-* headers, and conftest disables the limiter
    # so the ordinary suite never exercises that path.
    # Found by /qa on 2026-08-07.
    from app.core.ratelimit import limiter

    alice_h, _ = await _setup_pair(client, db)
    limiter.enabled = True
    try:
        res = await client.post(
            "/api/community/conversations",
            json={"recipient_handle": "bob"},
            headers=alice_h,
        )
        assert res.status_code == 201, res.text
        assert "x-ratelimit-limit" in res.headers

        res = await client.post(
            f"/api/community/conversations/{res.json()['id']}/messages",
            json={"body": "limiter on"},
            headers=alice_h,
        )
        assert res.status_code == 201, res.text
        assert "x-ratelimit-limit" in res.headers
    finally:
        limiter.enabled = False
