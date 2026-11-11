"""Audit event trail: use-case write points + the superuser read endpoint.

The rollback-survival API test is the load-bearing one: it pins the
autonomous-transaction design — a login failure 401s (rolling back the
request transaction) yet its audit row must still be committed.
"""

import uuid

import pytest
from sqlalchemy import select

from app.domains.audit.domain import AuditEvent, actions
from app.domains.billing.application.dtos import CreditPackPurchased
from app.domains.billing.application.use_cases import SyncBillingEvent
from tests.helpers import (
    PASSWORD,
    login,
    make_superuser,
    register,
    register_and_login,
)
from tests.test_login_lockout import FakeAudit, FakeTracker, make_login, make_user

pytestmark = pytest.mark.asyncio


# ── Use-case write points (fakes) ────────────────────────────────────


async def test_login_success_records_event_with_client_context():
    audit = FakeAudit()
    use_case, _ = make_login(make_user(), FakeTracker(), audit)
    await use_case.execute("user@example.com", PASSWORD, ip="1.2.3.4", user_agent="pytest-ua")
    assert [e.action for e in audit.events] == [actions.LOGIN_SUCCEEDED]
    event = audit.events[0]
    assert event.actor_user_id is not None
    assert event.ip == "1.2.3.4"
    assert event.user_agent == "pytest-ua"


async def test_login_failure_records_event_with_email_meta():
    audit = FakeAudit()
    use_case, _ = make_login(None, FakeTracker(), audit)
    with pytest.raises(Exception):
        await use_case.execute("Ghost@Example.com", PASSWORD, ip="1.2.3.4")
    assert [e.action for e in audit.events] == [actions.LOGIN_FAILED]
    assert audit.events[0].meta == {"email": "ghost@example.com"}
    assert audit.events[0].actor_user_id is None


async def test_lockout_records_both_events():
    audit = FakeAudit()
    tracker = FakeTracker()
    tracker.fails["user@example.com|unknown"] = 4
    use_case, _ = make_login(make_user(), tracker, audit)
    with pytest.raises(Exception):
        await use_case.execute("user@example.com", "wrong-password1")
    assert [e.action for e in audit.events] == [actions.LOCKOUT_TRIGGERED, actions.LOGIN_FAILED]
    assert audit.events[0].meta == {"email": "user@example.com", "scope": "client"}


class FakeCredits:
    def __init__(self, *, already: bool = False) -> None:
        self.already = already
        self.grants = []

    async def already_granted(self, idempotency_key: str) -> bool:
        return self.already

    async def grant(self, org_id, amount, description, user_id=None, idempotency_key=None):
        self.grants.append(idempotency_key)


def make_purchase() -> CreditPackPurchased:
    return CreditPackPurchased(
        org_id=uuid.uuid4(),
        pack_name="Starter",
        credits=100,
        session_id="cs_test_123",
        purchaser_email="buyer@example.com",
    )


async def test_credit_pack_purchase_records_event():
    audit = FakeAudit()
    await SyncBillingEvent(credits=FakeCredits(), audit=audit).execute(make_purchase())
    assert [e.action for e in audit.events] == [actions.CREDIT_PACK_PURCHASED]
    event = audit.events[0]
    assert event.meta["session_id"] == "cs_test_123"
    assert event.organization_id is not None
    assert event.actor_user_id is None  # webhook context — no signed-in actor


async def test_credit_pack_redelivery_does_not_double_log():
    audit = FakeAudit()
    await SyncBillingEvent(credits=FakeCredits(already=True), audit=audit).execute(make_purchase())
    assert audit.events == []


# ── API (real recorder, test DB) ─────────────────────────────────────


async def test_login_writes_success_event(client, db):
    user, _ = await register_and_login(client, "audited@example.com")
    rows = (
        (await db.execute(select(AuditEvent).where(AuditEvent.action == actions.LOGIN_SUCCEEDED)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].actor_user_id == uuid.UUID(user["id"])


async def test_failed_login_event_survives_request_rollback(client, db):
    await register(client, "audited@example.com")
    res = await login(client, "audited@example.com", "wrong-password1")
    assert res.status_code == 401
    rows = (
        (await db.execute(select(AuditEvent).where(AuditEvent.action == actions.LOGIN_FAILED)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].meta == {"email": "audited@example.com"}


async def test_audit_endpoint_superuser_only(client, db):
    user, headers = await register_and_login(client, "admin@example.com")
    res = await client.get("/api/admin/audit-events", headers=headers)
    assert res.status_code == 403, res.text

    await make_superuser(db, user["id"])
    res = await client.get("/api/admin/audit-events", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] >= 1
    actions_seen = {item["action"] for item in body["items"]}
    assert actions.LOGIN_SUCCEEDED in actions_seen
    # Filter narrows to one action.
    res = await client.get(
        "/api/admin/audit-events",
        params={"action": actions.LOGIN_FAILED},
        headers=headers,
    )
    assert res.status_code == 200
    assert all(item["action"] == actions.LOGIN_FAILED for item in res.json()["items"])
