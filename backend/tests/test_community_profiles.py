"""Unit + API tests for community profiles, directory, and the feature gate."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.community.application.use_cases import (
    GetMemberByHandle,
    JoinCommunity,
    ListDirectory,
    UpdateMyProfile,
)
from app.domains.community.domain import (
    CommunityBanned,
    CommunityMembership,
    CommunityProfile,
    HandleTaken,
    MembershipTier,
    NotACommunityMember,
    ProfileNotFound,
    SubscriptionStatus,
)
from tests.helpers import make_superuser, register_and_login


class FakeProfileRepo:
    def __init__(self, memberships: "FakeMembershipRepo") -> None:
        self.items: list[CommunityProfile] = []
        self.memberships = memberships

    async def add(self, profile: CommunityProfile) -> None:
        self.items.append(profile)

    async def get_by_user(self, user_id):
        return next((p for p in self.items if p.user_id == user_id), None)

    async def get_by_handle(self, handle):
        return next((p for p in self.items if p.handle == handle), None)

    def _tier(self, user_id) -> MembershipTier:
        m = next((m for m in self.memberships.items if m.user_id == user_id), None)
        return m.tier if m else MembershipTier.FREE

    def _visible(self):
        banned = {m.user_id for m in self.memberships.items if m.is_banned}
        return [p for p in self.items if not p.is_hidden and p.user_id not in banned]

    async def list_directory(self, *, search, limit, offset):
        rows = self._visible()
        if search:
            s = search.lower()
            rows = [p for p in rows if s in p.handle.lower() or s in p.display_name.lower()]
        return [(p, self._tier(p.user_id)) for p in rows[offset : offset + limit]], len(rows)

    async def get_visible_by_handle(self, handle):
        p = next((p for p in self._visible() if p.handle == handle), None)
        return (p, self._tier(p.user_id)) if p else None


class FakeMembershipRepo:
    def __init__(self) -> None:
        self.items: list[CommunityMembership] = []

    async def add(self, membership: CommunityMembership) -> None:
        self.items.append(membership)

    async def get_by_user(self, user_id):
        return next((m for m in self.items if m.user_id == user_id), None)

    async def get_by_subscription_id(self, subscription_id):
        return next(
            (m for m in self.items if m.stripe_subscription_id == subscription_id),
            None,
        )


def make_repos():
    memberships = FakeMembershipRepo()
    return FakeProfileRepo(memberships), memberships


# ---------------------------------------------------------------- use cases


async def test_join_creates_profile_and_free_membership():
    profiles, memberships = make_repos()
    user_id = uuid.uuid4()
    profile, membership = await JoinCommunity(profiles, memberships).execute(
        user_id, handle="Ada_L", display_name="  Ada  ", bio=None, avatar_url=None
    )
    assert profile.handle == "ada_l"  # normalized to lowercase
    assert profile.display_name == "Ada"
    assert membership.tier is MembershipTier.FREE
    assert membership.subscription_status is SubscriptionStatus.NONE


async def test_join_is_idempotent():
    profiles, memberships = make_repos()
    user_id = uuid.uuid4()
    join = JoinCommunity(profiles, memberships)
    first, _ = await join.execute(
        user_id, handle="original", display_name="Me", bio=None, avatar_url=None
    )
    second, _ = await join.execute(
        user_id, handle="different", display_name="Other", bio=None, avatar_url=None
    )
    assert second.id == first.id
    assert second.handle == "original"
    assert len(profiles.items) == 1


async def test_join_rejects_taken_handle():
    profiles, memberships = make_repos()
    await JoinCommunity(profiles, memberships).execute(
        uuid.uuid4(), handle="taken", display_name="A", bio=None, avatar_url=None
    )
    with pytest.raises(HandleTaken):
        await JoinCommunity(profiles, memberships).execute(
            uuid.uuid4(), handle="TAKEN", display_name="B", bio=None, avatar_url=None
        )


async def test_banned_user_cannot_rejoin_or_update():
    profiles, memberships = make_repos()
    user_id = uuid.uuid4()
    _, membership = await JoinCommunity(profiles, memberships).execute(
        user_id, handle="banned_user", display_name="B", bio=None, avatar_url=None
    )
    membership.ban(by=uuid.uuid4())
    with pytest.raises(CommunityBanned):
        await JoinCommunity(profiles, memberships).execute(
            user_id, handle="banned_user", display_name="B", bio=None, avatar_url=None
        )
    with pytest.raises(CommunityBanned):
        await UpdateMyProfile(profiles, memberships).execute(user_id, updates={"bio": "hi"})


async def test_update_requires_membership():
    profiles, memberships = make_repos()
    with pytest.raises(NotACommunityMember):
        await UpdateMyProfile(profiles, memberships).execute(uuid.uuid4(), updates={"bio": "hi"})


async def test_update_handle_conflict_and_change():
    profiles, memberships = make_repos()
    a, b = uuid.uuid4(), uuid.uuid4()
    join = JoinCommunity(profiles, memberships)
    await join.execute(a, handle="alpha", display_name="A", bio=None, avatar_url=None)
    await join.execute(b, handle="beta", display_name="B", bio=None, avatar_url=None)

    update = UpdateMyProfile(profiles, memberships)
    # Re-sending your own handle is fine.
    profile = await update.execute(a, updates={"handle": "ALPHA"})
    assert profile.handle == "alpha"
    # Taking another member's handle is not.
    with pytest.raises(HandleTaken):
        await update.execute(a, updates={"handle": "beta"})


async def test_directory_excludes_hidden_and_banned():
    profiles, memberships = make_repos()
    join = JoinCommunity(profiles, memberships)
    visible_id, hidden_id, banned_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await join.execute(visible_id, handle="visible", display_name="V", bio=None, avatar_url=None)
    hidden, _ = await join.execute(
        hidden_id, handle="hidden", display_name="H", bio=None, avatar_url=None
    )
    _, banned_m = await join.execute(
        banned_id, handle="banned", display_name="B", bio=None, avatar_url=None
    )
    hidden.is_hidden = True
    banned_m.ban(by=uuid.uuid4())

    items, total = await ListDirectory(profiles).execute(search=None, limit=10, offset=0)
    assert total == 1
    assert [p.handle for p, _ in items] == ["visible"]

    with pytest.raises(ProfileNotFound):
        await GetMemberByHandle(profiles).execute("hidden")
    with pytest.raises(ProfileNotFound):
        await GetMemberByHandle(profiles).execute("banned")


async def test_directory_search_matches_handle_and_name():
    profiles, memberships = make_repos()
    join = JoinCommunity(profiles, memberships)
    await join.execute(
        uuid.uuid4(), handle="jdoe", display_name="Jane Doe", bio=None, avatar_url=None
    )
    await join.execute(
        uuid.uuid4(), handle="other", display_name="Someone", bio=None, avatar_url=None
    )

    items, total = await ListDirectory(profiles).execute(search="doe", limit=10, offset=0)
    assert total == 1 and items[0][0].handle == "jdoe"


# ---------------------------------------------------------------- entity: premium window


def _membership(**overrides) -> CommunityMembership:
    m = CommunityMembership(user_id=uuid.uuid4())
    for key, value in overrides.items():
        setattr(m, key, value)
    return m


def test_is_premium_states():
    now = datetime.now(UTC)
    active = _membership(tier=MembershipTier.PREMIUM, subscription_status=SubscriptionStatus.ACTIVE)
    assert active.is_premium(grace_days=3) is True

    in_grace = _membership(
        tier=MembershipTier.PREMIUM,
        subscription_status=SubscriptionStatus.PAST_DUE,
        current_period_end=now - timedelta(days=1),
    )
    assert in_grace.is_premium(grace_days=3) is True

    past_grace = _membership(
        tier=MembershipTier.PREMIUM,
        subscription_status=SubscriptionStatus.PAST_DUE,
        current_period_end=now - timedelta(days=5),
    )
    assert past_grace.is_premium(grace_days=3) is False

    free = _membership()
    assert free.is_premium(grace_days=3) is False

    banned = _membership(tier=MembershipTier.PREMIUM, subscription_status=SubscriptionStatus.ACTIVE)
    banned.ban(by=uuid.uuid4())
    assert banned.is_premium(grace_days=3) is False


# ---------------------------------------------------------------- API


async def enable_community(client, db) -> None:
    user, headers = await register_and_login(client, "flag-flipper@example.com")
    await make_superuser(db, user["id"])
    res = await client.put("/api/admin/flags/community", json={"enabled": True}, headers=headers)
    assert res.status_code == 200, res.text


JOIN_BODY = {"handle": "tester", "display_name": "Test Member", "bio": "Hi there"}


async def test_all_routes_404_when_flag_off(client):
    _, headers = await register_and_login(client, "gated@example.com")
    for method, path in [
        ("get", "/api/community/me"),
        ("post", "/api/community/profile"),
        ("patch", "/api/community/profile"),
        ("get", "/api/community/members"),
        ("get", "/api/community/members/someone"),
    ]:
        res = await getattr(client, method)(
            path, headers=headers, **({"json": JOIN_BODY} if method != "get" else {})
        )
        assert res.status_code == 404, f"{method} {path}: {res.status_code}"
        assert res.json()["code"] == "ERR_FLAG_002"


async def test_join_and_me_and_directory_flow(client, db):
    await enable_community(client, db)
    _, headers = await register_and_login(client, "joiner@example.com")

    # Not joined yet: profile is null, not an error.
    me = (await client.get("/api/community/me", headers=headers)).json()
    assert me == {"profile": None, "membership": None}

    res = await client.post("/api/community/profile", json=JOIN_BODY, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["profile"]["handle"] == "tester"
    assert body["membership"]["tier"] == "free"
    assert body["membership"]["is_premium"] is False

    # Directory sees the member; search works; self-lookup by handle works.
    _, other_headers = await register_and_login(client, "viewer@example.com")
    page = (await client.get("/api/community/members?search=test", headers=other_headers)).json()
    assert page["total"] == 1
    assert page["items"][0]["handle"] == "tester"
    member = (await client.get("/api/community/members/tester", headers=other_headers)).json()
    assert member["display_name"] == "Test Member"


async def test_duplicate_handle_409(client, db):
    await enable_community(client, db)
    _, first = await register_and_login(client, "first@example.com")
    await client.post("/api/community/profile", json=JOIN_BODY, headers=first)

    _, second = await register_and_login(client, "second@example.com")
    res = await client.post("/api/community/profile", json=JOIN_BODY, headers=second)
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_COMM_002"


async def test_profile_update(client, db):
    await enable_community(client, db)
    _, headers = await register_and_login(client, "editor@example.com")
    await client.post("/api/community/profile", json=JOIN_BODY, headers=headers)

    res = await client.patch(
        "/api/community/profile", json={"display_name": "Renamed", "bio": None}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["display_name"] == "Renamed"
    assert res.json()["bio"] is None


async def test_invalid_handle_422(client, db):
    await enable_community(client, db)
    _, headers = await register_and_login(client, "badhandle@example.com")
    res = await client.post(
        "/api/community/profile",
        json={"handle": "no spaces!", "display_name": "X"},
        headers=headers,
    )
    assert res.status_code == 422


# ── Security hardening: verified-email gate + avatar URL allow-list ──


async def test_unverified_user_cannot_join_community(client, db):
    await enable_community(client, db)
    _, headers = await register_and_login(client, "unverified@example.com", verified=False)

    res = await client.post(
        "/api/community/profile",
        json={"handle": "spammer", "display_name": "Spam"},
        headers=headers,
    )
    assert res.status_code == 403, res.text
    # Reads stay open so the app can render the "verify to join" state.
    assert (await client.get("/api/community/me", headers=headers)).status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "http://example.com/a.png",
        "//example.com/a.png",
        "https://exa mple.com/a.png",
    ],
)
async def test_avatar_url_must_be_https(client, db, url):
    await enable_community(client, db)
    _, headers = await register_and_login(client, "member@example.com")

    res = await client.post(
        "/api/community/profile",
        json={"handle": "member_one", "display_name": "Member", "avatar_url": url},
        headers=headers,
    )
    assert res.status_code == 422, res.text


async def test_https_avatar_url_is_accepted_and_blank_clears(client, db):
    await enable_community(client, db)
    _, headers = await register_and_login(client, "member@example.com")

    res = await client.post(
        "/api/community/profile",
        json={
            "handle": "member_one",
            "display_name": "Member",
            "avatar_url": "https://cdn.example.com/a.png",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["profile"]["avatar_url"] == "https://cdn.example.com/a.png"

    res = await client.patch(
        "/api/community/profile", json={"avatar_url": "javascript:alert(1)"}, headers=headers
    )
    assert res.status_code == 422
    res = await client.patch("/api/community/profile", json={"avatar_url": ""}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["avatar_url"] is None
