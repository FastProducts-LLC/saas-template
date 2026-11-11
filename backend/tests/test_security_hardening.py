"""Security hardening regression tests: JWT key separation / claims /
rotation, impersonation limits, lockout + webhook behavior when their safe
defaults are unavailable, baseline response headers, and email link shape."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.config import settings
from app.domains.auth.infrastructure.lockout import RedisLoginAttemptTracker
from app.domains.emails.infrastructure.webhooks import ResendWebhookVerifier
from tests.helpers import make_superuser, register_and_login

STRONG_OLD = "o" * 48
STRONG_NEW = "n" * 48


# ── JWT classes, claims, rotation ────────────────────────────────────


def test_tokens_carry_issuer_audience_and_unique_id():
    user_id = str(uuid.uuid4())
    a, b = security.create_access_token(user_id), security.create_access_token(user_id)
    assert a != b  # jti makes every token distinct
    claims = security.decode_access_claims(a)
    assert claims["sub"] == user_id
    assert claims["aud"] == "access"
    assert claims["iss"] == settings.token_issuer
    assert claims["jti"]


def test_action_token_never_verifies_as_access_token_and_vice_versa():
    user_id = str(uuid.uuid4())
    action = security.create_action_token(user_id, "password_reset", timedelta(minutes=5))
    access = security.create_access_token(user_id)

    assert security.decode_access_token(action) is None
    assert security.decode_action_token(access, "password_reset") is None
    # Even an action token that lies about its type is signed with the action
    # key, so the access decoder rejects the signature outright.
    forged = security.create_action_token(user_id, "access", timedelta(minutes=5))
    assert security.decode_access_token(forged) is None


def test_action_token_purpose_is_bound():
    user_id = str(uuid.uuid4())
    token = security.create_action_token(user_id, "email_verify", timedelta(minutes=5))
    assert security.decode_action_token(token, "email_verify")["sub"] == user_id
    assert security.decode_action_token(token, "password_reset") is None


def test_action_token_claims_cannot_override_reserved_fields():
    token = security.create_action_token(
        "real-user", "email_verify", timedelta(minutes=5), {"sub": "someone-else", "pwf": "x"}
    )
    payload = security.decode_action_token(token, "email_verify")
    assert payload["sub"] == "real-user" and payload["pwf"] == "x"


def test_legacy_token_signed_with_the_raw_secret_is_rejected():
    now = datetime.now(UTC)
    legacy = jwt.encode(
        {"sub": "u", "type": "access", "iat": now, "exp": now + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS256",
    )
    assert security.decode_access_token(legacy) is None


def test_token_from_another_deployment_is_rejected(monkeypatch):
    token = security.create_access_token("u")
    monkeypatch.setattr(settings, "frontend_url", "https://some-other-env.example.com")
    assert security.decode_access_token(token) is None


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "access_token_ttl_minutes", -1)
    assert security.decode_access_token(security.create_access_token("u")) is None


def test_secret_rotation_keeps_old_tokens_valid_until_previous_is_dropped(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", STRONG_OLD)
    old_access = security.create_access_token("u")
    old_action = security.create_action_token("u", "email_verify", timedelta(minutes=5))

    # Rotate: new key signs, old key still verifies.
    monkeypatch.setattr(settings, "secret_key", STRONG_NEW)
    assert security.decode_access_token(old_access) is None
    monkeypatch.setattr(settings, "secret_key_previous", STRONG_OLD)
    assert security.decode_access_token(old_access) == "u"
    assert security.decode_action_token(old_action, "email_verify")["sub"] == "u"
    assert security.decode_access_token(security.create_access_token("u")) == "u"

    # Rotation finished.
    monkeypatch.setattr(settings, "secret_key_previous", "")
    assert security.decode_access_token(old_access) is None


# ── Impersonation sessions can look, not mint credentials ────────────


async def test_impersonation_session_cannot_change_password_or_mint_api_keys(client, db):
    admin, admin_headers = await register_and_login(client, "root@example.com")
    await make_superuser(db, admin["id"])
    target, target_headers = await register_and_login(client, "target@example.com")
    org = await client.post(
        "/api/orgs",
        json={"name": "Target Org", "intended_use": "Automated test suite usage"},
        headers=target_headers,
    )
    assert org.status_code == 201, org.text
    org_id = org.json()["id"]

    res = await client.post(f"/api/admin/users/{target['id']}/impersonate", headers=admin_headers)
    assert res.status_code == 200, res.text
    imp_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    # Still a working session for looking around...
    me = await client.get("/api/auth/me", headers=imp_headers)
    assert me.status_code == 200 and me.json()["email"] == "target@example.com"

    # ...but not for creating credentials that outlive it.
    res = await client.post(
        f"/api/orgs/{org_id}/api-keys", json={"name": "backdoor"}, headers=imp_headers
    )
    assert res.status_code == 403, res.text
    assert res.json()["code"] == "ERR_AUTH_007"
    res = await client.post(
        "/api/auth/change-password",
        json={
            "current_password": "whatever-it-is-1",
            "password": "brand-new-pass7",
            "password_confirmation": "brand-new-pass7",
        },
        headers=imp_headers,
    )
    assert res.status_code == 403 and res.json()["code"] == "ERR_AUTH_007"

    # The real owner is unaffected.
    res = await client.post(
        f"/api/orgs/{org_id}/api-keys", json={"name": "mine"}, headers=target_headers
    )
    assert res.status_code == 201, res.text


# ── Lockout when Redis is down: degraded, never open ─────────────────


class _DeadRedis:
    def __getattr__(self, name):
        async def boom(*args, **kwargs):
            raise ConnectionError("redis down")

        return boom


async def test_lockout_still_enforced_when_redis_is_down(monkeypatch):
    from app.core import error_handling

    monkeypatch.setattr(error_handling, "_redis_client", lambda: _DeadRedis())
    tracker = RedisLoginAttemptTracker(window_seconds=900, lockout_seconds=900)

    assert await tracker.lockout_remaining("a@example.com") == 0
    counts = [await tracker.record_failure("a@example.com") for _ in range(5)]
    assert counts == [1, 2, 3, 4, 5]
    await tracker.lock("a@example.com")
    assert 0 < await tracker.lockout_remaining("a@example.com") <= 900
    # Other accounts are unaffected; a successful login clears the state.
    assert await tracker.lockout_remaining("b@example.com") == 0
    await tracker.clear("a@example.com")
    assert await tracker.lockout_remaining("a@example.com") == 0
    assert await tracker.record_failure("a@example.com") == 1


async def test_login_locks_out_end_to_end_with_redis_down(client, monkeypatch):
    from app.core import error_handling
    from app.domains.auth.interface import deps as auth_deps
    from tests.helpers import PASSWORD, login, register

    await register(client)
    monkeypatch.setattr(
        auth_deps,
        "_login_attempts",
        RedisLoginAttemptTracker(window_seconds=900, lockout_seconds=900),
    )
    monkeypatch.setattr(error_handling, "_redis_client", lambda: _DeadRedis())

    for _ in range(settings.login_lockout_max_attempts):
        assert (await login(client, password="wrong-password-1")).status_code == 401
    res = await login(client, password=PASSWORD)
    assert res.status_code == 429 and res.json()["code"] == "ERR_AUTH_006"


def test_memory_fallback_is_bounded():
    from app.domains.auth.infrastructure.lockout import _MemoryAttempts

    mem = _MemoryAttempts(window_seconds=900, lockout_seconds=900)
    mem.MAX_KEYS = 50
    mem.lock("victim")
    for i in range(500):
        mem.record_failure(f"spray-{i}")
    assert len(mem._fails) <= 50
    assert mem.lockout_remaining("victim") > 0  # locks survive counter eviction


# ── Resend webhook: unsigned only on a genuinely local stack ─────────


def test_unsigned_webhook_rejected_when_dev_env_is_publicly_reachable(monkeypatch):
    verifier = ResendWebhookVerifier()
    monkeypatch.setattr(settings, "resend_webhook_secret", "")
    assert settings.is_local_dev and verifier.verify(b"{}", {}) is True

    # ENVIRONMENT left at "development" on a real host: must fail closed.
    monkeypatch.setattr(settings, "frontend_url", "https://app.acme.com")
    assert not settings.is_production and not settings.is_local_dev
    assert verifier.verify(b"{}", {}) is False


# ── Baseline response headers from the app itself ────────────────────


@pytest.mark.parametrize("path", ["/api/config", "/api/auth/me", "/api/definitely-not-a-route"])
async def test_every_response_carries_security_headers(client, path):
    res = await client.get(path)
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in res.headers["content-security-policy"]
    # HSTS only when ENVIRONMENT=production (never pin it on a dev hostname).
    assert "strict-transport-security" not in res.headers


async def test_security_headers_on_cors_preflight(client):
    res = await client.options(
        "/api/auth/login",
        headers={"Origin": settings.cors_origins[0], "Access-Control-Request-Method": "POST"},
    )
    assert res.headers["x-content-type-options"] == "nosniff"


def test_hsts_is_added_in_production(monkeypatch):
    from app.core import security_headers

    monkeypatch.setattr(settings, "environment", "production")
    names = [name for name, _ in security_headers._baseline_headers()]
    assert b"strict-transport-security" in names


# ── Email links keep the token out of the query string ───────────────


async def test_email_links_carry_the_token_in_the_fragment(monkeypatch):
    from app.domains.auth.domain import User
    from app.domains.auth.infrastructure import mailer as mailer_module

    sent: list[dict] = []

    async def fake_send(to, subject, *, text, html, tags=None, **kwargs):
        sent.append({"text": text, "html": html, "tags": tags})

    monkeypatch.setattr(mailer_module, "send_email", fake_send)
    user = User(email="u@example.com", password_hash="x", first_name="U", last_name="")
    mailer = mailer_module.TransactionalAuthMailer()

    await mailer.send_verification(user)
    await mailer.send_password_reset(user, {"pwf": "abc"})

    assert len(sent) == 2
    for message, path in zip(sent, ["/verify-email", "/reset-password"], strict=True):
        assert f"{settings.frontend_url}{path}#token=" in message["text"]
        assert "?token=" not in message["text"] and "?token=" not in message["html"]
