"""Shared test helpers: account/org builders and a Stripe webhook signer.

Kept out of conftest.py so suites import exactly what they use:

    from tests.helpers import register_and_login, create_org
"""

import hashlib
import hmac
import time
import uuid
from datetime import timedelta

PASSWORD = "correct-horse9"


def register_payload(email: str = "user@example.com", **overrides) -> dict:
    payload = {
        "first_name": "Test",
        "last_name": "User",
        "email": email,
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
        "terms_accepted": True,
        "marketing_opt_in": False,
    }
    payload.update(overrides)
    return payload


async def register(client, email: str = "user@example.com", **overrides) -> dict:
    res = await client.post("/api/auth/register", json=register_payload(email, **overrides))
    assert res.status_code == 201, res.text
    return res.json()


async def login(client, email: str = "user@example.com", password: str = PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def verify_email(client, user_id: str | uuid.UUID) -> None:
    """Mark the mailbox verified via the real verify-email endpoint."""
    from app.core.security import create_action_token
    from app.domains.auth.application.use_cases import PURPOSE_VERIFY_EMAIL

    token = create_action_token(str(user_id), PURPOSE_VERIFY_EMAIL, timedelta(hours=1))
    res = await client.post("/api/auth/verify-email", json={"token": token})
    assert res.status_code == 204, res.text


async def register_and_login(
    client, email: str = "user@example.com", *, verified: bool = True
) -> tuple[dict, dict]:
    """Register + optional verify + login; returns (user_body, auth_headers).

    Defaults to verified=True so EMAIL_VERIFICATION_GATE=sensitive routes work
    without every suite repeating the verify step. Pass verified=False to
    exercise the gate.
    """
    user = await register(client, email)
    if verified:
        await verify_email(client, user["id"])
    res = await login(client, email)
    assert res.status_code == 200, res.text
    return user, auth_headers(res.json()["access_token"])


async def create_org(client, headers: dict, name: str = "Acme") -> dict:
    res = await client.post(
        "/api/orgs",
        json={"name": name, "intended_use": "Automated test suite usage"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


async def make_superuser(db, user_id: str | uuid.UUID) -> None:
    """Flip the flag directly — there is deliberately no API for this."""
    from app.domains.auth.domain import User

    user = await db.get(User, uuid.UUID(str(user_id)))
    user.is_superuser = True
    await db.commit()


def stripe_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a real `stripe-signature` header value (t=<ts>,v1=<hmac>) so
    webhook tests exercise the actual verification path."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed = f"{ts}.{payload.decode()}"
    sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"
