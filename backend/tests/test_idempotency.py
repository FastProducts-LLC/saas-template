"""Idempotency middleware tests (Redis-backed; runs inside the dev container).

Focus: the fingerprint is scoped to a *stable caller identity* (JWT `sub`),
not the raw Authorization header, so a retry that arrives after a token
refresh replays the first response instead of re-executing it.

We exercise the real middleware end-to-end through `POST /api/orgs` — a cheap
mutating endpoint that returns 201 and is not in EXCLUDED_PATHS. Each test
uses a fresh random Idempotency-Key so reused keys can't collide across tests
(the Redis store is shared with the dev stack and persists between cases).
"""

import uuid

from app.core.security import create_access_token, decode_access_token
from tests.helpers import auth_headers, register_and_login

ORGS = "/api/orgs"


def _access_token_for(user_id: str, *, iat_skew_seconds: int = 0) -> str:
    """A second, byte-distinct but fully valid access token for `user_id`
    (every token carries a unique `jti`, so no clock skew is needed; the
    parameter is kept for call-site readability)."""
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id
    return token


def _idem_headers(headers: dict, key: str) -> dict:
    return {**headers, "Idempotency-Key": key}


def _org_payload(name: str) -> dict:
    return {"name": name, "intended_use": "Automated test suite usage"}


async def test_retry_after_token_refresh_replays_same_response(client):
    """Regression: same key + same user but a DIFFERENT valid access token
    (as happens after a 401-triggered refresh) must REPLAY, not re-execute."""
    _, headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    user_id = str(me["id"])

    # A second, distinct-but-valid access token for the same user — what the
    # frontend carries on its post-refresh retry (iat_skew forces a different
    # token byte-string).
    refreshed = auth_headers(_access_token_for(user_id, iat_skew_seconds=5))
    assert refreshed["Authorization"] != headers["Authorization"]

    key = str(uuid.uuid4())
    first = await client.post(
        ORGS,
        json=_org_payload("Acme"),
        headers=_idem_headers(headers, key),
    )
    assert first.status_code == 201, first.text
    assert "Idempotency-Replayed" not in first.headers

    second = await client.post(
        ORGS,
        json=_org_payload("Acme"),
        headers=_idem_headers(refreshed, key),
    )
    assert second.status_code == 201, second.text
    # Replayed: identical body to the first attempt, no second org created.
    assert second.json()["id"] == first.json()["id"]
    assert second.json() == first.json()

    orgs = (await client.get(ORGS, headers=headers)).json()
    assert len(orgs) == 1, "retry must not create a second org"


async def test_different_users_same_key_do_not_replay(client):
    """Same Idempotency-Key but different callers must both execute — one
    user can never replay another user's response by guessing the key."""
    _, headers_a = await register_and_login(client, email="a@idem-a.com")
    _, headers_b = await register_and_login(client, email="b@idem-b.com")

    key = str(uuid.uuid4())
    res_a = await client.post(
        ORGS,
        json=_org_payload("A-org"),
        headers=_idem_headers(headers_a, key),
    )
    res_b = await client.post(
        ORGS,
        json=_org_payload("B-org"),
        headers=_idem_headers(headers_b, key),
    )

    assert res_a.status_code == 201, res_a.text
    assert res_b.status_code == 201, res_b.text
    assert "Idempotency-Replayed" not in res_b.headers
    assert res_a.json()["id"] != res_b.json()["id"]
    assert res_a.json()["name"] == "A-org"
    assert res_b.json()["name"] == "B-org"

    orgs_a = (await client.get(ORGS, headers=headers_a)).json()
    orgs_b = (await client.get(ORGS, headers=headers_b)).json()
    assert [o["name"] for o in orgs_a] == ["A-org"]
    assert [o["name"] for o in orgs_b] == ["B-org"]


async def test_replayed_response_carries_replay_marker(client):
    """The cached replay is flagged with the middleware's `Idempotency-Replayed`
    header (and a fresh first attempt is not)."""
    _, headers = await register_and_login(client)
    key = str(uuid.uuid4())

    first = await client.post(
        ORGS,
        json=_org_payload("Acme"),
        headers=_idem_headers(headers, key),
    )
    assert first.status_code == 201, first.text
    assert first.headers.get("Idempotency-Replayed") is None

    replay = await client.post(
        ORGS,
        json=_org_payload("Acme"),
        headers=_idem_headers(headers, key),
    )
    assert replay.status_code == 201, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
