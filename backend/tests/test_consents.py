"""Unit + API tests for the consent audit trail."""

import uuid

import pytest

from app.domains.consents.application.use_cases import GetCurrentConsent, RecordConsent
from app.domains.consents.domain import ConsentEvent
from tests.helpers import register_and_login


class FakeConsentRepo:
    def __init__(self) -> None:
        self.items: list[ConsentEvent] = []

    async def add(self, event: ConsentEvent) -> None:
        self.items.append(event)

    async def latest_for_user(self, user_id: uuid.UUID) -> ConsentEvent | None:
        mine = [e for e in self.items if e.user_id == user_id]
        return max(mine, key=lambda e: e.created_at, default=None)


@pytest.mark.asyncio
async def test_record_consent_appends_immutable_events():
    repo = FakeConsentRepo()
    user_id = uuid.uuid4()

    first = await RecordConsent(repo).execute(
        user_id=user_id,
        analytics=True,
        policy_version="2026-07-09",
        ip_address="203.0.113.9",
        user_agent="pytest/1.0",
    )
    second = await RecordConsent(repo).execute(
        user_id=user_id, analytics=False, policy_version="2026-07-09"
    )

    # Both decisions survive as separate rows — withdrawal never erases the grant.
    assert len(repo.items) == 2
    assert first.analytics is True
    assert second.analytics is False
    assert first.ip_address == "203.0.113.9"
    assert first.user_agent == "pytest/1.0"

    latest = await GetCurrentConsent(repo).execute(user_id=user_id)
    assert latest is second


@pytest.mark.asyncio
async def test_record_consent_clamps_oversized_metadata():
    repo = FakeConsentRepo()
    event = await RecordConsent(repo).execute(
        user_id=uuid.uuid4(),
        analytics=True,
        policy_version=" 2026-07-09 " + "x" * 64,
        user_agent="a" * 999,
    )
    assert len(event.policy_version) <= 32
    assert event.user_agent is not None and len(event.user_agent) == 255


@pytest.mark.asyncio
async def test_current_consent_is_none_for_undecided_user():
    latest = await GetCurrentConsent(FakeConsentRepo()).execute(user_id=uuid.uuid4())
    assert latest is None


@pytest.mark.asyncio
async def test_consent_api_roundtrip(client):
    _, headers = await register_and_login(client, "consent@example.com")

    # Undecided user → null.
    res = await client.get("/api/consent", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() is None

    res = await client.post(
        "/api/consent",
        json={"analytics": True, "policy_version": "2026-07-09"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["analytics"] is True
    assert body["policy_version"] == "2026-07-09"

    # Withdrawal appends; GET reflects the latest decision.
    res = await client.post(
        "/api/consent",
        json={"analytics": False, "policy_version": "2026-07-09"},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    res = await client.get("/api/consent", headers=headers)
    assert res.status_code == 200
    assert res.json()["analytics"] is False


@pytest.mark.asyncio
async def test_consent_api_requires_auth(client):
    res = await client.get("/api/consent")
    assert res.status_code == 401
    res = await client.post(
        "/api/consent", json={"analytics": True, "policy_version": "2026-07-09"}
    )
    assert res.status_code == 401
