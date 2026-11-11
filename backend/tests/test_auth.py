"""Auth API tests: registration, sessions, email verification, password reset."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_action_token, hash_token
from app.domains.auth.application.use_cases import (
    PURPOSE_PASSWORD_RESET,
    PURPOSE_VERIFY_EMAIL,
)
from app.domains.auth.domain import RefreshToken, User
from tests.helpers import PASSWORD, login, register, register_payload, verify_email

REFRESH_COOKIE = "refresh_token"


# ── Registration ─────────────────────────────────────────────────────


async def test_register_returns_user(client):
    body = await register(client)
    assert body["email"] == "user@example.com"
    assert body["name"] == "Test User"
    assert body["email_verified"] is False
    assert "password" not in body and "password_hash" not in body


async def test_register_normalizes_email_case(client, db):
    await register(client, email="MiXeD@Example.COM")
    user = (await db.execute(select(User))).scalar_one()
    assert user.email == "mixed@example.com"


async def test_register_rejects_weak_passwords(client):
    for bad in ["short1", "allletters", "12345678", "password123", "abcdefgh1"]:
        res = await client.post(
            "/api/auth/register",
            json=register_payload(password=bad, password_confirmation=bad),
        )
        assert res.status_code == 400, bad
        assert res.json()["code"] == "ERR_VAL_003", bad


async def test_register_rejects_password_mismatch(client):
    res = await client.post(
        "/api/auth/register", json=register_payload(password_confirmation=PASSWORD + "x")
    )
    assert res.status_code == 400
    assert res.json()["code"] == "ERR_VAL_004"


async def test_register_requires_terms(client):
    res = await client.post("/api/auth/register", json=register_payload(terms_accepted=False))
    assert res.status_code == 400
    assert res.json()["code"] == "ERR_VAL_005"


async def test_register_rejects_duplicate_email(client):
    await register(client)
    res = await client.post("/api/auth/register", json=register_payload())
    assert res.status_code == 409
    assert res.json()["code"] == "ERR_VAL_002"


# ── Sessions: login / me / refresh / logout ──────────────────────────


async def test_login_returns_session_and_sets_refresh_cookie(client):
    await register(client)
    res = await login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["user"]["email"] == "user@example.com"
    assert REFRESH_COOKIE in res.cookies


async def test_login_rejects_wrong_password(client):
    await register(client)
    res = await login(client, password="wrong-pass1")
    assert res.status_code == 401
    assert res.json()["code"] == "ERR_AUTH_001"


async def test_me_requires_token(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


async def test_me_returns_current_user(client):
    await register(client)
    token = (await login(client)).json()["access_token"]
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "user@example.com"


async def test_refresh_rotates_token(client):
    await register(client)
    await login(client)
    old_refresh = client.cookies[REFRESH_COOKIE]

    res = await client.post("/api/auth/refresh")
    assert res.status_code == 200
    assert res.json()["access_token"]
    assert client.cookies[REFRESH_COOKIE] != old_refresh

    # The pre-rotation token is revoked: replaying it must fail.
    client.cookies.set(REFRESH_COOKIE, old_refresh, path="/api/auth")
    res = await client.post("/api/auth/refresh")
    assert res.status_code == 401
    assert res.json()["code"] == "ERR_AUTH_002"


async def test_refresh_rejects_already_revoked_token():
    """Rotation race: with the row lock held, the loser re-reads the token as
    already revoked, so `get_valid` returns None and refresh -> SessionExpired.
    Modelled here at the use-case level: a repo whose `get_valid` never returns
    a revoked token (exactly what `with_for_update` + `revoked_at IS NULL`
    guarantees once the winner commits)."""
    from app.domains.auth.application.use_cases import RefreshSession
    from app.domains.auth.domain import RefreshToken, SessionExpired

    class FakeRefreshTokens:
        def __init__(self, token: RefreshToken) -> None:
            self._token = token
            self.added: list[RefreshToken] = []

        async def get_valid(self, token_hash: str) -> RefreshToken | None:
            # Mirrors the SQL guard: a revoked token is invisible.
            if self._token.token_hash != token_hash or self._token.revoked_at is not None:
                return None
            return self._token

        async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
            return self._token if self._token.token_hash == token_hash else None

        async def add(self, token: RefreshToken) -> None:
            self.added.append(token)

    token = RefreshToken(user_id=uuid.uuid4(), token_hash="h:raw", expires_at=_far_future())
    repo = FakeRefreshTokens(token)
    revoker, audit = _FakeSessionRevoker(), _FakeAudit()
    use_case = RefreshSession(repo, _FakeTokens(), 30, revoker, audit)

    # First rotation succeeds and revokes the token.
    await use_case.execute("raw")
    assert token.revoked_at is not None
    assert len(repo.added) == 1

    # The concurrent loser sees a revoked token -> SessionExpired, no new token.
    try:
        await use_case.execute("raw")
        raise AssertionError("expected SessionExpired")
    except SessionExpired:
        pass
    assert len(repo.added) == 1  # no second token minted
    # ...and an immediate replay is the benign race, NOT theft: nobody is
    # logged out because two tabs refreshed at once.
    assert revoker.revoked == [] and audit.events == []


class _FakeTokens:
    def hash_token(self, raw: str) -> str:
        return f"h:{raw}"

    def create_access_token(self, user_id: str) -> str:
        return f"access:{user_id}"

    def new_opaque_token(self) -> tuple[str, str]:
        return ("raw-new", "h:raw-new")


class _FakeSessionRevoker:
    def __init__(self) -> None:
        self.revoked: list[uuid.UUID] = []

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self.revoked.append(user_id)


class _FakeAudit:
    def __init__(self) -> None:
        self.events: list = []

    async def record(self, event) -> None:
        self.events.append(event)


class _StaleTokenRepo:
    """A repo holding one no-longer-valid token (invisible to get_valid)."""

    def __init__(self, token: RefreshToken) -> None:
        self._token = token

    async def get_valid(self, token_hash: str) -> RefreshToken | None:
        return None

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self._token if self._token.token_hash == token_hash else None

    async def add(self, token: RefreshToken) -> None:
        raise AssertionError("a stale token must never mint a successor")


async def _replay_stale(token: RefreshToken, raw: str = "raw"):
    from app.domains.auth.application.use_cases import RefreshSession
    from app.domains.auth.domain import SessionExpired

    revoker, audit = _FakeSessionRevoker(), _FakeAudit()
    use_case = RefreshSession(_StaleTokenRepo(token), _FakeTokens(), 30, revoker, audit)
    try:
        await use_case.execute(raw, ip="203.0.113.9", user_agent="evil/1.0")
        raise AssertionError("expected SessionExpired")
    except SessionExpired:
        pass
    return revoker, audit


async def test_replaying_a_rotated_token_revokes_every_session():
    """Reuse detection: a token consumed by rotation shows up again after the
    race window -> two parties hold the chain -> kill all of the user's sessions."""
    from datetime import UTC, datetime

    from app.domains.audit.domain import actions

    token = RefreshToken(user_id=uuid.uuid4(), token_hash="h:raw", expires_at=_far_future())
    token.rotate()
    token.rotated_at = datetime.now(UTC) - timedelta(minutes=5)

    revoker, audit = await _replay_stale(token)

    assert revoker.revoked == [token.user_id]
    assert [e.action for e in audit.events] == [actions.REFRESH_TOKEN_REUSED]
    assert audit.events[0].actor_user_id == token.user_id
    assert audit.events[0].ip == "203.0.113.9"


async def test_replaying_a_logged_out_or_bulk_revoked_token_is_not_reuse():
    """Tokens revoked by logout / password change / admin revoke-all are
    stale, not stolen: a second device waking up after a password change must
    not log out the device that changed it."""
    from datetime import UTC, datetime

    token = RefreshToken(user_id=uuid.uuid4(), token_hash="h:raw", expires_at=_far_future())
    token.revoke()
    token.revoked_at = datetime.now(UTC) - timedelta(minutes=5)

    revoker, audit = await _replay_stale(token)

    assert revoker.revoked == [] and audit.events == []


async def test_unknown_refresh_token_is_not_reuse():
    token = RefreshToken(user_id=uuid.uuid4(), token_hash="h:other", expires_at=_far_future())
    token.rotate()
    token.rotated_at = token.rotated_at - timedelta(minutes=5)

    revoker, audit = await _replay_stale(token, raw="never-issued")

    assert revoker.revoked == [] and audit.events == []


async def test_refresh_token_reuse_kills_the_whole_chain(client, db):
    """End to end: the thief's descendant token dies when the stolen ancestor
    is replayed, and the revocation survives the 401's rollback."""
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.domains.audit.domain import AuditEvent, actions

    await register(client)
    await login(client)
    stolen = client.cookies[REFRESH_COOKIE]
    assert (await client.post("/api/auth/refresh")).status_code == 200
    descendant = client.cookies[REFRESH_COOKIE]

    # Move the rotation outside the race-grace window.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(stolen))
        .values(rotated_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await db.commit()

    client.cookies.set(REFRESH_COOKIE, stolen, path="/api/auth")
    res = await client.post("/api/auth/refresh")
    assert res.status_code == 401
    assert res.json()["code"] == "ERR_AUTH_002"

    # The newest token in the chain is dead too.
    client.cookies.set(REFRESH_COOKIE, descendant, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401
    active = (
        (await db.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))))
        .scalars()
        .all()
    )
    assert active == []
    events = (
        (
            await db.execute(
                select(AuditEvent).where(AuditEvent.action == actions.REFRESH_TOKEN_REUSED)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1

    # Not a lockout: signing in again works.
    assert (await login(client)).status_code == 200


async def test_immediate_replay_of_rotated_token_keeps_other_sessions(client):
    """Inside the grace window a replay is only rejected (rotation race)."""
    await register(client)
    await login(client)
    old = client.cookies[REFRESH_COOKIE]
    assert (await client.post("/api/auth/refresh")).status_code == 200
    current = client.cookies[REFRESH_COOKIE]

    client.cookies.set(REFRESH_COOKIE, old, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401

    client.cookies.set(REFRESH_COOKIE, current, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 200


async def test_stale_token_after_password_change_does_not_kill_new_session(client):
    await register(client)
    token = (await login(client)).json()["access_token"]
    other_device = client.cookies[REFRESH_COOKIE]
    new_password = "brand-new-pass7"
    res = await client.post(
        "/api/auth/change-password",
        json={
            "current_password": PASSWORD,
            "password": new_password,
            "password_confirmation": new_password,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    fresh = client.cookies[REFRESH_COOKIE]

    client.cookies.set(REFRESH_COOKIE, other_device, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401

    client.cookies.set(REFRESH_COOKIE, fresh, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 200


async def test_oversized_credentials_are_rejected_before_hashing(client):
    await register(client)
    res = await client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "x" * 129}
    )
    assert res.status_code == 422
    token = (await login(client)).json()["access_token"]
    res = await client.post(
        "/api/auth/change-password",
        json={
            "current_password": "x" * 129,
            "password": "brand-new-pass7",
            "password_confirmation": "brand-new-pass7",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def _far_future():
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC) + timedelta(days=30)


async def test_logout_revokes_refresh_token(client):
    await register(client)
    await login(client)
    old_refresh = client.cookies[REFRESH_COOKIE]

    res = await client.post("/api/auth/logout")
    assert res.status_code == 204

    client.cookies.set(REFRESH_COOKIE, old_refresh, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


# ── Email verification ───────────────────────────────────────────────


async def test_verify_email_marks_user_verified(client, db):
    body = await register(client)
    token = create_action_token(body["id"], PURPOSE_VERIFY_EMAIL, timedelta(hours=1))

    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 204

    user = await db.get(User, uuid.UUID(body["id"]))
    assert user.email_verified_at is not None


async def test_verify_email_rejects_bad_token(client):
    res = await client.post("/api/auth/verify-email", json={"token": "garbage"})
    assert res.status_code == 400
    assert res.json()["code"] == "ERR_AUTH_004"


async def test_verify_email_rejects_wrong_purpose_token(client):
    body = await register(client)
    # A reset token must not work as a verification token.
    token = create_action_token(body["id"], PURPOSE_PASSWORD_RESET, timedelta(hours=1))
    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 400


# ── Password reset ───────────────────────────────────────────────────


async def _reset_token_for(db, email: str) -> str:
    """Craft the same purpose-scoped token forgot_password() emails out."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    fingerprint = hash_token(user.password_hash)[:16]
    return create_action_token(
        str(user.id), PURPOSE_PASSWORD_RESET, timedelta(minutes=30), {"pwd": fingerprint}
    )


async def test_forgot_password_never_reveals_account_existence(client):
    res = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert res.status_code == 204


async def test_reset_password_flow(client, db):
    await register(client)
    await login(client)
    token = await _reset_token_for(db, "user@example.com")
    new_password = "brand-new-pass7"

    res = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": new_password, "password_confirmation": new_password},
    )
    assert res.status_code == 204

    # Old password dead, new password works.
    assert (await login(client)).status_code == 401
    assert (await login(client, password=new_password)).status_code == 200

    # All pre-reset sessions are revoked, and the link proved mailbox control.
    user = (await db.execute(select(User).where(User.email == "user@example.com"))).scalar_one()
    assert user.email_verified_at is not None
    tokens = (
        (await db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id)))
        .scalars()
        .all()
    )
    pre_reset = [t for t in tokens if t.revoked_at is None]
    # Only the post-reset login's token may remain active.
    assert len(pre_reset) <= 1


async def test_reset_token_is_single_use(client, db):
    await register(client)
    token = await _reset_token_for(db, "user@example.com")
    new_password = "brand-new-pass7"

    first = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": new_password, "password_confirmation": new_password},
    )
    assert first.status_code == 204

    # The password hash changed, so the embedded fingerprint no longer matches.
    replay = await client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "password": "another-pass8",
            "password_confirmation": "another-pass8",
        },
    )
    assert replay.status_code == 400
    assert replay.json()["code"] == "ERR_AUTH_004"


# ── Profile ──────────────────────────────────────────────────────────


async def test_update_me_changes_name_only(client):
    await register(client)
    token = (await login(client)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.patch("/api/auth/me", json={"first_name": "New"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "New User"
    assert body["marketing_opt_in"] is False  # untouched fields stay put


async def test_change_password_requires_current_password(client):
    await register(client)
    token = (await login(client)).json()["access_token"]

    res = await client.post(
        "/api/auth/change-password",
        json={
            "current_password": "wrong-pass1",
            "password": "brand-new-pass7",
            "password_confirmation": "brand-new-pass7",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401
    assert res.json()["code"] == "ERR_AUTH_001"


async def test_change_password_rotates_sessions(client):
    await register(client)
    token = (await login(client)).json()["access_token"]
    pre_change_refresh = client.cookies[REFRESH_COOKIE]
    new_password = "brand-new-pass7"

    res = await client.post(
        "/api/auth/change-password",
        json={
            "current_password": PASSWORD,
            "password": new_password,
            "password_confirmation": new_password,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["access_token"]  # caller stays signed in

    # The fresh refresh cookie works; the pre-change one is revoked.
    assert (await client.post("/api/auth/refresh")).status_code == 200
    client.cookies.set(REFRESH_COOKIE, pre_change_refresh, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401

    assert (await login(client, password=PASSWORD)).status_code == 401
    assert (await login(client, password=new_password)).status_code == 200


# ── Mobile clients (X-Client: mobile — body-based refresh tokens) ────

MOBILE = {"X-Client": "mobile"}


async def test_web_login_never_returns_refresh_token_in_body(client):
    await register(client)
    res = await login(client)
    assert res.status_code == 200
    assert res.json()["refresh_token"] is None
    assert REFRESH_COOKIE in res.cookies


async def test_mobile_login_returns_refresh_token_in_body_without_cookie(client):
    await register(client)
    res = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": PASSWORD},
        headers=MOBILE,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["refresh_token"]
    assert body["access_token"]
    assert REFRESH_COOKIE not in res.cookies


async def test_mobile_refresh_rotates_body_token(client):
    await register(client)
    res = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": PASSWORD},
        headers=MOBILE,
    )
    old_refresh = res.json()["refresh_token"]

    res = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["refresh_token"] and body["refresh_token"] != old_refresh
    assert REFRESH_COOKIE not in res.cookies

    # Rotation revoked the old token.
    res = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 401

    # The rotated token still works.
    res = await client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert res.status_code == 200


async def test_web_refresh_response_keeps_token_out_of_body(client):
    await register(client)
    await login(client)
    res = await client.post("/api/auth/refresh")
    assert res.status_code == 200
    assert res.json()["refresh_token"] is None
    assert REFRESH_COOKIE in res.cookies


async def test_mobile_logout_revokes_body_token(client):
    await register(client)
    res = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": PASSWORD},
        headers=MOBILE,
    )
    refresh = res.json()["refresh_token"]

    res = await client.post("/api/auth/logout", json={"refresh_token": refresh})
    assert res.status_code == 204

    res = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert res.status_code == 401


async def test_mobile_change_password_returns_refresh_token_in_body(client):
    await register(client)
    res = await client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": PASSWORD},
        headers=MOBILE,
    )
    token = res.json()["access_token"]
    new_password = "brand-new-pass7"

    res = await client.post(
        "/api/auth/change-password",
        json={
            "current_password": PASSWORD,
            "password": new_password,
            "password_confirmation": new_password,
        },
        headers={"Authorization": f"Bearer {token}", **MOBILE},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert REFRESH_COOKIE not in res.cookies

    res = await client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert res.status_code == 200


# ── Password-changed security notice ─────────────────────────────────


def _capture_auth_mail(monkeypatch) -> list[tuple[str, str]]:
    """Record (recipient, tag type) for every auth-mailer send."""
    from app.domains.auth.infrastructure import mailer as mailer_module

    sent: list[tuple[str, str]] = []

    async def _capture(to, subject, **kwargs):
        sent.append((to, (kwargs.get("tags") or {}).get("type", "")))

    monkeypatch.setattr(mailer_module, "send_email", _capture)
    return sent


async def _change_password(client, token: str, current: str = PASSWORD):
    return await client.post(
        "/api/auth/change-password",
        json={
            "current_password": current,
            "password": "brand-new-pass7",
            "password_confirmation": "brand-new-pass7",
        },
        headers={"Authorization": f"Bearer {token}"},
    )


async def test_change_password_sends_security_notice(client, monkeypatch):
    await register(client)
    token = (await login(client)).json()["access_token"]
    sent = _capture_auth_mail(monkeypatch)

    assert (await _change_password(client, token)).status_code == 200
    assert sent == [("user@example.com", "password_changed")]


async def test_failed_change_password_sends_no_notice(client, monkeypatch):
    await register(client)
    token = (await login(client)).json()["access_token"]
    sent = _capture_auth_mail(monkeypatch)

    res = await _change_password(client, token, current="not-the-password1")
    assert res.status_code != 200
    assert sent == []


async def test_reset_password_sends_security_notice(client, db, monkeypatch):
    await register(client)
    token = await _reset_token_for(db, "user@example.com")
    sent = _capture_auth_mail(monkeypatch)

    res = await client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "password": "brand-new-pass7",
            "password_confirmation": "brand-new-pass7",
        },
    )
    assert res.status_code == 204
    assert sent == [("user@example.com", "password_changed")]


async def test_password_changed_notice_escapes_name_and_links_to_reset():
    from types import SimpleNamespace

    from app.domains.auth.infrastructure import email_content

    user = SimpleNamespace(first_name="<b>Eve</b>")
    subject, text, html = email_content.password_changed_email(
        user, "https://app.test/forgot-password"
    )
    assert "password was changed" in subject
    assert "https://app.test/forgot-password" in text
    assert "https://app.test/forgot-password" in html
    assert "<b>Eve</b>" not in html and "&lt;b&gt;Eve&lt;/b&gt;" in html


# ── Verify-first signup (SIGNUP_ENUMERATION_PROTECTION) ──────────────


class _RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def __getattr__(self, name: str):
        async def _send(user, *args, **kwargs) -> None:
            self.sent.append((name, user.email))

        return _send


@pytest.fixture
def verify_first(monkeypatch):
    from app.domains.auth.interface import deps as auth_deps

    mailer = _RecordingMailer()
    monkeypatch.setattr(settings, "signup_enumeration_protection", True)
    monkeypatch.setattr(auth_deps, "_mailer", mailer)
    return mailer


async def _user_id(db, email: str) -> uuid.UUID:
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def test_verify_first_register_answers_identically_for_new_and_taken_email(
    client, db, verify_first
):
    taken = await client.post("/api/auth/register", json=register_payload("taken@example.com"))
    await verify_email(client, await _user_id(db, "taken@example.com"))

    fresh = await client.post("/api/auth/register", json=register_payload("fresh@example.com"))
    again = await client.post(
        "/api/auth/register",
        json=register_payload(
            "taken@example.com",
            password="Attacker_pass99",
            password_confirmation="Attacker_pass99",
            first_name="Mallory",
        ),
    )
    for res in (taken, fresh, again):
        assert res.status_code == 202, res.text
        assert res.json() == {"verification_required": True}
    # The owner hears about it by email; the response said nothing.
    assert verify_first.sent[-1] == ("send_account_exists_notice", "taken@example.com")

    # The second attempt changed nothing: the owner's password still works,
    # the submitted one does not.
    assert (await login(client, "taken@example.com")).status_code == 200
    res = await login(client, "taken@example.com", "Attacker_pass99")
    assert res.status_code == 401 and res.json()["code"] == "ERR_AUTH_001"


async def test_verify_first_unconfirmed_login_looks_like_a_wrong_password(client, db, verify_first):
    """Closes register-then-login: a just-created account and an address
    that already had one (so the submitted password is wrong) both answer
    ERR_AUTH_001."""
    await client.post("/api/auth/register", json=register_payload("new@example.com"))
    res = await login(client, "new@example.com")
    assert res.status_code == 401 and res.json()["code"] == "ERR_AUTH_001"

    await verify_email(client, await _user_id(db, "new@example.com"))
    assert (await login(client, "new@example.com")).status_code == 200


async def test_verify_first_reregistering_unconfirmed_email_resends_the_link(client, verify_first):
    await client.post("/api/auth/register", json=register_payload("slow@example.com"))
    res = await client.post("/api/auth/register", json=register_payload("slow@example.com"))
    assert res.status_code == 202
    assert [name for name, _ in verify_first.sent] == [
        "send_welcome_with_verification",
        "send_verification",
    ]
