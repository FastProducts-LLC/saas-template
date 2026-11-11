"""Emails webhook tests: Resend (Svix) signature → marketing-preferences sync,
suppression, event log.

The webhook lives at POST /api/webhooks/resend. Signature verification fails
open in development when no secret is configured (manual curl testing) and fails
closed in production. When a secret IS set, verification runs through the Resend
SDK (resend.Webhooks.verify). On a verified `contact.unsubscribed` /
`contact.updated(unsubscribed)` event, the matching user's marketing_opt_in is
flipped off. Every `email.*` event lands in email_events (deduped by svix-id);
`email.bounced` suppresses the address, `email.complained` suppresses AND
revokes marketing opt-in. Suppressed users get no transactional email.
"""

import uuid

import resend
from sqlalchemy import func, select

from app.core.config import settings
from app.domains.auth.domain import User
from app.domains.emails.domain import EmailEvent
from tests.helpers import register

WEBHOOK_URL = "/api/webhooks/resend"


async def _opt_in_user(client, db, email: str = "fan@example.com") -> User:
    """Register a user who opted into marketing, return the persisted entity."""
    body = await register(client, email=email, marketing_opt_in=True)
    user = await db.get(User, uuid.UUID(body["id"]))
    assert user.marketing_opt_in is True
    return user


# ── Dev fail-open: unsubscribe syncs marketing preferences ───────────


async def test_contact_unsubscribed_flips_opt_in_off(client, db):
    # Empty resend_webhook_secret + development → signature check is skipped.
    assert not settings.resend_webhook_secret
    assert not settings.is_production
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "contact.unsubscribed", "data": {"email": user.email}},
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"received": True}

    await db.refresh(user)
    assert user.marketing_opt_in is False


async def test_contact_unsubscribed_matches_email_case_insensitively(client, db):
    user = await _opt_in_user(client, db, email="mixed@example.com")

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "contact.unsubscribed", "data": {"email": "MIXED@Example.COM"}},
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is False


# ── contact.updated ──────────────────────────────────────────────────


async def test_contact_updated_unsubscribed_flips_opt_in_off(client, db):
    # contact.updated only opts out when data.unsubscribed is truthy.
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={
            "type": "contact.updated",
            "data": {"email": user.email, "unsubscribed": True},
        },
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is False


async def test_contact_updated_still_subscribed_is_noop(client, db):
    # unsubscribed=False → the branch is skipped; marketing opt-in is untouched.
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={
            "type": "contact.updated",
            "data": {"email": user.email, "unsubscribed": False},
        },
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is True


# ── Suppression: bounces and complaints ──────────────────────────────


async def test_email_bounced_suppresses_but_keeps_opt_in(client, db):
    # A hard bounce means the address is dead — suppress it, but bouncing is
    # not an opt-out: marketing opt-in survives (they may fix their email later).
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={
            "type": "email.bounced",
            "data": {"to": [user.email], "bounce_type": "hard"},
        },
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.email_suppressed is True
    assert user.marketing_opt_in is True


async def test_email_bounced_legacy_email_address_field(client, db):
    # Older payload shape: address under email_address instead of to[].
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={
            "type": "email.bounced",
            "data": {"email_address": user.email, "bounce_type": "hard"},
        },
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.email_suppressed is True


async def test_email_complained_suppresses_and_revokes_opt_in(client, db):
    # A spam complaint means "never email me": suppress AND opt out.
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "email.complained", "data": {"to": [user.email]}},
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.email_suppressed is True
    assert user.marketing_opt_in is False


async def test_suppressed_user_gets_no_transactional_email(client, db, monkeypatch):
    # The mailer guard: once suppressed, transactional sends are skipped.
    from app.domains.auth.infrastructure import mailer as mailer_module

    user = await _opt_in_user(client, db)
    user.email_suppressed = True

    sent = []

    async def _capture(to, subject, **kwargs):
        sent.append(to)

    monkeypatch.setattr(mailer_module, "send_email", _capture)
    await mailer_module.TransactionalAuthMailer().send_verification(user)
    assert sent == []

    user.email_suppressed = False
    await mailer_module.TransactionalAuthMailer().send_verification(user)
    assert sent == [user.email]


# ── Event log: every email.* event persisted, deduped by svix-id ─────


async def _event_count(db) -> int:
    return await db.scalar(select(func.count()).select_from(EmailEvent))


async def test_email_event_is_persisted(client, db):
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={
            "type": "email.delivered",
            "data": {
                "to": [user.email],
                "subject": "Welcome!",
                "email_id": "re_123",
                "created_at": "2026-07-09T00:00:00.000Z",
            },
        },
        headers={"svix-id": "msg_delivered_1"},
    )
    assert res.status_code == 200, res.text

    event = (await db.execute(select(EmailEvent))).scalar_one()
    assert event.event == "email.delivered"
    assert event.recipient == user.email
    assert event.subject == "Welcome!"
    assert event.email_id == "re_123"
    assert event.svix_id == "msg_delivered_1"
    assert event.occurred_at is not None


async def test_duplicate_svix_id_stores_one_event(client, db):
    # Svix delivery is at-least-once; a redelivered message must not double-log.
    user = await _opt_in_user(client, db)
    body = {"type": "email.opened", "data": {"to": [user.email]}}

    for _ in range(2):
        res = await client.post(WEBHOOK_URL, json=body, headers={"svix-id": "msg_dup"})
        assert res.status_code == 200, res.text

    assert await _event_count(db) == 1


async def test_missing_svix_id_still_ingests(client, db):
    # No svix-id header (e.g. manual dashboard test) → still store the event.
    user = await _opt_in_user(client, db)
    body = {"type": "email.sent", "data": {"to": [user.email]}}

    for _ in range(2):
        res = await client.post(WEBHOOK_URL, json=body)
        assert res.status_code == 200, res.text

    # Without an id there is nothing to dedupe on — both rows land.
    assert await _event_count(db) == 2


# ── Resilience: unknown email, unknown event, bad JSON ───────────────


async def test_unknown_email_is_accepted_without_state_change(client, db):
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "contact.unsubscribed", "data": {"email": "stranger@example.com"}},
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is True


async def test_unknown_event_type_is_ignored(client, db):
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "domain.updated", "data": {"email": user.email}},
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is True
    assert await _event_count(db) == 0


async def test_invalid_json_body_returns_400(client):
    res = await client.post(
        WEBHOOK_URL,
        content=b"not json{",
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400, res.text


# ── Production fail-closed (no secret) ────────────────────────────────


async def test_production_with_no_secret_fails_closed(client, db, monkeypatch):
    # In production an unconfigured secret must reject the webhook (401), never
    # silently accept unsigned requests.
    monkeypatch.setattr(settings, "environment", "production")
    assert settings.is_production and not settings.resend_webhook_secret
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "contact.unsubscribed", "data": {"email": user.email}},
    )
    assert res.status_code == 401, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is True  # never processed


# ── Signature verification (secret configured) ───────────────────────


async def test_bad_signature_rejected(client, db, monkeypatch):
    # With a secret set, verification runs; a failing verify → 401.
    monkeypatch.setattr(settings, "resend_webhook_secret", "whsec_test")

    def _boom(payload):  # resend.Webhooks.verify(dict) → raises on mismatch
        raise ValueError("signature mismatch")

    monkeypatch.setattr(resend.Webhooks, "verify", _boom)
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "contact.unsubscribed", "data": {"email": user.email}},
        headers={
            "svix-id": "msg_1",
            "svix-timestamp": "1",
            "svix-signature": "v1,bogus",
        },
    )
    assert res.status_code == 401, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is True  # never processed


async def test_good_signature_processes_event(client, db, monkeypatch):
    # With a secret set and verify passing, the event is processed normally.
    monkeypatch.setattr(settings, "resend_webhook_secret", "whsec_test")

    def _ok(payload):
        return None  # SDK returns the verified payload; truthiness unused

    monkeypatch.setattr(resend.Webhooks, "verify", _ok)
    user = await _opt_in_user(client, db)

    res = await client.post(
        WEBHOOK_URL,
        json={"type": "contact.unsubscribed", "data": {"email": user.email}},
        headers={
            "svix-id": "msg_1",
            "svix-timestamp": "1",
            "svix-signature": "v1,valid",
        },
    )
    assert res.status_code == 200, res.text

    await db.refresh(user)
    assert user.marketing_opt_in is False


# ── Suppression at the send chokepoint (every slice's mail) ──────────


class _RecordingProvider:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_email(self, *, to, subject, text=None, html=None, tags=None) -> None:
        self.sent.append(to)


async def test_suppression_lookup_matches_only_flagged_users(client, db):
    from app.domains.auth.interface.deps import build_marketing_preferences_repository

    user = await _opt_in_user(client, db)
    repo = build_marketing_preferences_repository(db)
    assert await repo.is_email_suppressed(user.email) is False

    user.email_suppressed = True
    await db.flush()
    assert await repo.is_email_suppressed(user.email) is True
    assert await repo.is_email_suppressed(user.email.upper()) is True  # case-insensitive
    # An address with no account (e.g. an invitee) is never suppressed.
    assert await repo.is_email_suppressed("stranger@example.com") is False


async def test_send_task_drops_mail_to_suppressed_address(monkeypatch):
    # Invitations, receipts and low-balance alerts never see a User object,
    # so the guard has to hold inside the send task itself.
    import app.core.email as email_module
    from app.core.email import suppression, tasks

    provider = _RecordingProvider()
    monkeypatch.setattr(email_module, "get_provider", lambda: provider)

    async def _check(email: str) -> bool:
        return email == "dead@example.com"

    monkeypatch.setattr(suppression, "_check", _check)

    await tasks._send(to="dead@example.com", subject="Receipt", text="x", html=None, tags=None)
    await tasks._send(to="alive@example.com", subject="Receipt", text="x", html=None, tags=None)
    assert provider.sent == ["alive@example.com"]


async def test_send_task_sends_when_no_lookup_registered(monkeypatch):
    import app.core.email as email_module
    from app.core.email import suppression, tasks

    provider = _RecordingProvider()
    monkeypatch.setattr(email_module, "get_provider", lambda: provider)
    monkeypatch.setattr(suppression, "_check", None)

    await tasks._send(to="anyone@example.com", subject="Hi", text="x", html=None, tags=None)
    assert provider.sent == ["anyone@example.com"]


async def test_failing_suppression_lookup_blocks_the_send(monkeypatch):
    # A DB blip must retry the task, not mail an address we couldn't check.
    import pytest

    import app.core.email as email_module
    from app.core.email import suppression, tasks

    provider = _RecordingProvider()
    monkeypatch.setattr(email_module, "get_provider", lambda: provider)

    async def _boom(email: str) -> bool:
        raise RuntimeError("db down")

    monkeypatch.setattr(suppression, "_check", _boom)
    with pytest.raises(RuntimeError):
        await tasks._send(to="a@example.com", subject="Hi", text="x", html=None, tags=None)
    assert provider.sent == []


def test_worker_import_registers_the_suppression_lookup():
    import importlib

    from app.core.email import suppression
    from app.domains.emails import tasks as emails_tasks
    from app.domains.emails.worker import is_address_suppressed

    importlib.reload(emails_tasks)  # what Celery autodiscovery does at start-up
    assert suppression._check is is_address_suppressed


# ── Subject sanitization ─────────────────────────────────────────────


def test_clean_subject_collapses_line_breaks_and_control_chars():
    from app.core.email import clean_subject

    assert clean_subject("Join Acme\r\nBcc: x@evil.test") == "Join Acme Bcc: x@evil.test"
    assert clean_subject("a\x00b c\td") == "a b c d"
    assert clean_subject("  Plain — subject ✓ ") == "Plain — subject ✓"


async def test_send_email_enqueues_a_deliverable_subject(monkeypatch):
    """A CR/LF that reached a subject (e.g. an org name stored before names
    were validated) must not make the worker's message build blow up."""
    from email.message import EmailMessage

    from app.core import email as email_module
    from app.core.email import tasks

    sent = {}
    monkeypatch.setattr(tasks.send_email_task, "delay", lambda **kw: sent.update(kw))
    await email_module.send_email("a@example.com", "Invite to Evil\r\nBcc: x@evil.test", text="hi")
    msg = EmailMessage()
    msg["Subject"] = sent["subject"]  # raises ValueError on a linefeed
    assert "\n" not in sent["subject"] and "\r" not in sent["subject"]
