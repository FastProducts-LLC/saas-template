"""Product analytics: first-party activity_events ingest, server-truth capture,
opt-out, retention purge, and the slices that emit server events.

Unit tests construct use cases with in-memory fakes; API tests hit the real
endpoint against the test database (and real Redis for the rate gate).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domains.analytics.application.use_cases import (
    CaptureServerEvent,
    PurgeExpiredActivityEvents,
    RecordClientEvent,
)
from app.domains.analytics.domain import CLIENT_EVENTS, SERVER_EVENTS, ActivityEvent
from app.domains.analytics.domain.policy import (
    MAX_BODY_BYTES,
    MAX_PROPERTY_KEYS,
    MAX_STRING_CHARS,
    sanitize_properties,
)
from app.domains.analytics.infrastructure.orm import activity_events_table
from app.domains.analytics.infrastructure.rate_gate import RedisIngestRateGate
from app.domains.analytics.infrastructure.repositories import SqlAlchemyActivityEventRepository
from app.domains.analytics.worker import purge_expired_activity_events
from app.domains.auth.infrastructure.orm import users_table
from app.domains.billing.application.dtos import CreditPackPurchased
from app.domains.billing.application.use_cases import SyncBillingEvent
from app.domains.community.application.use_cases import ApplyCommunitySubscriptionEvent
from app.domains.community.domain.entities import CommunityMembership, SubscriptionStatus
from app.domains.credits.domain import CreditAction
from app.domains.generations.application.use_cases import FinalizeGeneration
from app.domains.generations.domain import Generation, GenerationStatus
from tests.helpers import register_and_login

# ── fakes ────────────────────────────────────────────────────────────


class FakeEvents:
    def __init__(self, *, opted_out: bool = False) -> None:
        self.items: list[ActivityEvent] = []
        self.opted_out = opted_out

    async def add(self, event: ActivityEvent) -> None:
        self.items.append(event)

    async def is_opted_out(self, user_id: uuid.UUID) -> bool:
        return self.opted_out


class FakeGate:
    def __init__(self, allow: bool = True) -> None:
        self._allow = allow

    async def allow(self, user_id: uuid.UUID) -> bool:
        return self._allow


class FakeTracker:
    """Stands in for CaptureServerEvent behind the slices' ActivityTracker ports."""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID | None, str, dict | None]] = []

    async def capture_server_event(self, user_id, event, properties=None):
        self.calls.append((user_id, event, properties))

    @property
    def names(self) -> list[str]:
        return [name for _, name, _ in self.calls]


async def _rows(db) -> list:
    result = await db.execute(select(activity_events_table).order_by(activity_events_table.c.id))
    return list(result.mappings())


# ── registry invariants ──────────────────────────────────────────────


def test_registry_sets_are_disjoint_and_named_sanely():
    assert CLIENT_EVENTS and SERVER_EVENTS
    assert not (CLIENT_EVENTS & SERVER_EVENTS)
    for name in CLIENT_EVENTS | SERVER_EVENTS:
        assert name == name.lower() and len(name) <= 40
    # The activation event must stay server-truth (never forgeable by a browser).
    assert "generation_completed" in SERVER_EVENTS


# ── property sanitization (privacy floor backstop) ───────────────────


def test_sanitize_keeps_scalars_and_drops_everything_else():
    clean = sanitize_properties(
        {
            "role": "admin",
            "count": 3,
            "ratio": 0.5,
            "flag": True,
            "nothing": None,
            "nested": {"a": 1},
            "listy": [1, 2],
            "nan": float("nan"),
            "inf": float("inf"),
            "Bad-Key": "x",
            "": "x",
            7: "x",
        }
    )
    assert clean == {"role": "admin", "count": 3, "ratio": 0.5, "flag": True, "nothing": None}


def test_sanitize_truncates_strings_and_caps_key_count():
    clean = sanitize_properties({"long": "x" * 500})
    assert clean == {"long": "x" * MAX_STRING_CHARS}
    many = sanitize_properties({f"k{i}": i for i in range(60)})
    assert len(many) == MAX_PROPERTY_KEYS


def test_sanitize_root_shapes():
    assert sanitize_properties(None) == {}
    assert sanitize_properties({}) == {}
    assert sanitize_properties([1]) is None
    assert sanitize_properties("str") is None


# ── RecordClientEvent (unit) ─────────────────────────────────────────


async def _record(events, *, gate=None, opted_out=False, event="org_created", properties=None):
    return await RecordClientEvent(events, gate or FakeGate()).execute(
        user_id=uuid.uuid4(), opted_out=opted_out, event=event, properties=properties
    )


async def test_client_event_recorded_with_client_source():
    events = FakeEvents()
    assert await _record(events, properties={"role": "member"}) is True
    assert [(e.event, e.source, e.properties) for e in events.items] == [
        ("org_created", "client", {"role": "member"})
    ]


async def test_client_cannot_write_server_truth_or_unknown_names():
    events = FakeEvents()
    for name in ("credit_pack_purchased", "generation_completed", "made_up", "", None, 7, {}):
        assert await _record(events, event=name) is False
    assert events.items == []


async def test_client_event_dropped_when_opted_out_rate_limited_or_malformed():
    events = FakeEvents()
    assert await _record(events, opted_out=True) is False
    assert await _record(events, gate=FakeGate(allow=False)) is False
    assert await _record(events, properties=["not", "an", "object"]) is False
    assert events.items == []


# ── CaptureServerEvent (unit) ────────────────────────────────────────


async def test_server_event_recorded_with_server_source_and_sanitized_props():
    events = FakeEvents()
    user_id = uuid.uuid4()
    ok = await CaptureServerEvent(events).capture_server_event(
        user_id, "generation_completed", {"kind": "image", "junk": {"nested": 1}}
    )
    assert ok is True
    (event,) = events.items
    assert (event.user_id, event.event, event.source) == (user_id, "generation_completed", "server")
    assert event.properties == {"kind": "image"}


async def test_server_event_skips_unattributable_unregistered_and_opted_out():
    events = FakeEvents()
    capture = CaptureServerEvent(events).capture_server_event
    assert await capture(None, "generation_completed") is False  # API-key actor
    assert await capture(uuid.uuid4(), "generation_complete_typo") is False
    assert await capture(uuid.uuid4(), "org_created") is False  # client-only name
    assert (
        await CaptureServerEvent(FakeEvents(opted_out=True)).capture_server_event(
            uuid.uuid4(), "generation_completed"
        )
        is False
    )
    assert events.items == []


# ── ingest endpoint (API) ────────────────────────────────────────────


async def test_ingest_requires_authentication(client, db):
    res = await client.post("/api/events", json={"event": "org_created"})
    assert res.status_code == 401
    assert await _rows(db) == []


async def test_ingest_stores_event_for_the_session_user_only(client, db):
    user, headers = await register_and_login(client)
    someone_else = str(uuid.uuid4())
    res = await client.post(
        "/api/events",
        headers=headers,
        json={
            "event": "invite_sent",
            "properties": {"role": "admin"},
            "user_id": someone_else,  # must be ignored
            "source": "server",  # must be ignored
        },
    )
    assert res.status_code == 204
    assert res.content == b""
    (row,) = await _rows(db)
    assert str(row["user_id"]) == user["id"]
    assert row["event"] == "invite_sent"
    assert row["source"] == "client"
    assert row["properties"] == {"role": "admin"}
    assert row["created_at"] is not None


async def test_ingest_answers_204_but_stores_nothing_for_bad_input(client, db):
    _, headers = await register_and_login(client)
    raw_headers = {**headers, "Content-Type": "application/json"}
    bodies = [
        b"",  # empty
        b"not json",
        b"\xff\xfe",  # not utf-8
        b"[]",  # not an object
        b'"org_created"',
        b"{}",  # no event
        b'{"event": "credit_pack_purchased"}',  # server-truth name from a browser
        b'{"event": "generation_completed", "properties": {"kind": "image"}}',
        b'{"event": "does_not_exist"}',
        b'{"event": ["org_created"]}',
        b'{"event": "org_created", "properties": "nope"}',
        b'{"event": "org_created", "pad": "' + b"x" * MAX_BODY_BYTES + b'"}',  # > 8 KB
    ]
    for body in bodies:
        res = await client.post("/api/events", headers=raw_headers, content=body)
        assert res.status_code == 204, body[:40]
    assert await _rows(db) == []


async def test_ingest_missing_properties_is_an_empty_bag(client, db):
    _, headers = await register_and_login(client)
    res = await client.post("/api/events", headers=headers, json={"event": "user_logged_in"})
    assert res.status_code == 204
    (row,) = await _rows(db)
    assert row["properties"] == {}


async def test_opt_out_round_trips_and_stops_both_client_and_server_events(client, db):
    user, headers = await register_and_login(client)
    assert user["analytics_opt_out"] is False

    res = await client.patch("/api/auth/me", headers=headers, json={"analytics_opt_out": True})
    assert res.status_code == 200 and res.json()["analytics_opt_out"] is True
    # Unrelated partial updates leave the flag alone.
    res = await client.patch("/api/auth/me", headers=headers, json={"first_name": "Renamed"})
    assert res.json()["analytics_opt_out"] is True

    res = await client.post("/api/events", headers=headers, json={"event": "org_created"})
    assert res.status_code == 204
    capture = CaptureServerEvent(SqlAlchemyActivityEventRepository(db))
    assert (
        await capture.capture_server_event(uuid.UUID(user["id"]), "generation_completed") is False
    )
    await db.commit()
    assert await _rows(db) == []

    # Opting back in resumes recording.
    await client.patch("/api/auth/me", headers=headers, json={"analytics_opt_out": False})
    await client.post("/api/events", headers=headers, json={"event": "org_created"})
    assert [r["event"] for r in await _rows(db)] == ["org_created"]


async def test_rate_gate_caps_events_per_user_per_minute(monkeypatch):
    # Pin the clock so the minute bucket can't roll over mid-test.
    monkeypatch.setattr(
        "app.domains.analytics.infrastructure.rate_gate.time.time", lambda: 1_900_000_000.0
    )
    gate = RedisIngestRateGate(per_minute=3)
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    assert [await gate.allow(user_a) for _ in range(5)] == [True, True, True, False, False]
    assert await gate.allow(user_b) is True  # independent budget per user


async def test_rate_gate_fails_open_without_redis(monkeypatch):
    def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.core.error_handling._redis_client", boom)
    assert await RedisIngestRateGate(per_minute=1).allow(uuid.uuid4()) is True


# ── persistence behaviour (real DB) ──────────────────────────────────


async def test_server_capture_persists_and_unknown_user_is_skipped(client, db):
    user, _ = await register_and_login(client)
    capture = CaptureServerEvent(SqlAlchemyActivityEventRepository(db))
    assert (
        await capture.capture_server_event(
            uuid.UUID(user["id"]), "credit_pack_purchased", {"pack": "growth", "credits": 500}
        )
        is True
    )
    assert await capture.capture_server_event(uuid.uuid4(), "credit_pack_purchased") is False
    await db.commit()
    (row,) = await _rows(db)
    assert row["source"] == "server"
    assert row["properties"] == {"pack": "growth", "credits": 500}


async def test_failed_event_insert_never_poisons_the_callers_transaction(client, test_engine):
    """A write for a vanished user (FK violation) must only unwind its own
    savepoint — the business change in the same transaction still commits."""
    user, _ = await register_and_login(client)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sessions() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE users SET first_name = 'Business' WHERE id = :id"), {"id": user["id"]}
            )
            repo = SqlAlchemyActivityEventRepository(session)
            await repo.add(ActivityEvent(user_id=uuid.uuid4(), event="org_created"))  # FK fails
            await repo.add(ActivityEvent(user_id=uuid.UUID(user["id"]), event="org_created"))
    async with sessions() as session:
        name = await session.scalar(
            select(users_table.c.first_name).where(users_table.c.id == uuid.UUID(user["id"]))
        )
        assert name == "Business"
        assert len(await _rows(session)) == 1


async def test_event_rolls_back_with_the_business_transaction(client, test_engine):
    """Server truth is atomic with the fact it records: no phantom purchase
    event when the surrounding transaction (e.g. the credit grant) rolls back."""
    user, _ = await register_and_login(client)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sessions() as session:
        capture = CaptureServerEvent(SqlAlchemyActivityEventRepository(session))
        assert (
            await capture.capture_server_event(uuid.UUID(user["id"]), "credit_pack_purchased")
            is True
        )
        await session.rollback()
    async with sessions() as session:
        assert await _rows(session) == []


async def test_deleting_the_account_cascades_its_events(client, db):
    user, headers = await register_and_login(client)
    await client.post("/api/events", headers=headers, json={"event": "org_created"})
    assert len(await _rows(db)) == 1
    await db.execute(users_table.delete().where(users_table.c.id == uuid.UUID(user["id"])))
    await db.commit()
    assert await _rows(db) == []


async def _seed_aged_events(db, user_id: str, ages_days: list[int]) -> None:
    now = datetime.now(UTC)
    await db.execute(
        insert(activity_events_table),
        [
            {
                "user_id": uuid.UUID(user_id),
                "event": "org_created",
                "source": "client",
                "properties": {},
                "created_at": now - timedelta(days=age),
            }
            for age in ages_days
        ],
    )
    await db.commit()


async def test_purge_is_batched_and_only_removes_rows_past_retention(client, db):
    user, _ = await register_and_login(client)
    await _seed_aged_events(db, user["id"], [800, 790, 780, 10, 0])
    purge = PurgeExpiredActivityEvents(SqlAlchemyActivityEventRepository(db), retention_days=730)
    assert await purge.execute(batch_size=2) == 2  # bounded per call
    assert await purge.execute(batch_size=2) == 1
    assert await purge.execute(batch_size=2) == 0
    await db.commit()
    assert await db.scalar(select(func.count()).select_from(activity_events_table)) == 2


async def test_purge_worker_loops_until_done_using_policy_retention(client, db, test_engine):
    user, _ = await register_and_login(client)
    # Policy retention is 730 days: 729 stays, 731 goes.
    await _seed_aged_events(db, user["id"], [900, 731, 729, 1])
    removed = await purge_expired_activity_events(async_sessionmaker(test_engine))
    assert removed == 2
    assert await purge_expired_activity_events(async_sessionmaker(test_engine)) == 0  # idempotent
    assert await db.scalar(select(func.count()).select_from(activity_events_table)) == 2


async def test_dau_and_funnel_queries_run_against_the_contract_columns(client, db):
    """The founder-metrics contract: activity_events(user_id, created_at)."""
    _, headers_a = await register_and_login(client, "a@example.com")
    _, headers_b = await register_and_login(client, "b@example.com")
    for headers, events in (
        (headers_a, ["org_created", "invite_sent"]),
        (headers_b, ["org_created"]),
    ):
        for event in events:
            await client.post("/api/events", headers=headers, json={"event": event})
    dau = await db.scalar(
        text(
            "SELECT count(DISTINCT user_id) FILTER (WHERE created_at >= now() - interval '1 day') "
            "FROM activity_events"
        )
    )
    assert dau == 2
    funnel = (
        await db.execute(
            text(
                "SELECT count(DISTINCT user_id) FILTER (WHERE event = 'org_created') AS created, "
                "count(DISTINCT user_id) FILTER (WHERE event = 'invite_sent') AS invited "
                "FROM activity_events WHERE created_at >= now() - interval '30 days'"
            )
        )
    ).one()
    assert (funnel.created, funnel.invited) == (2, 1)


# ── emitting slices (unit, fake tracker) ─────────────────────────────


class _GenRepo:
    def __init__(self, gen):
        self._gen = gen

    async def get(self, generation_id):
        return self._gen if generation_id == self._gen.id else None


class _Credits:
    async def capture(self, reservation_id):
        pass

    async def release(self, reservation_id, reason=None):
        pass


def _generation(**overrides) -> Generation:
    fields = {
        "organization_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "kind": CreditAction.IMAGE_NANO_BANANA,
        "model": "test-model",
        "prompt": "a secret prompt that must never reach analytics",
        "reservation_id": uuid.uuid4(),
        "credits_cost": 4,
    }
    fields.update(overrides)
    return Generation(**fields)


async def test_generation_success_emits_activation_event_once():
    gen, tracker = _generation(), FakeTracker()
    finalize = FinalizeGeneration(_GenRepo(gen), _Credits(), tracker)
    await finalize.execute(gen.id, file_path="org/x.png", mime_type="image/png")
    await finalize.execute(gen.id, file_path="org/x.png", mime_type="image/png")  # redelivery

    ((user_id, name, props),) = tracker.calls
    assert (user_id, name) == (gen.user_id, "generation_completed")
    assert props["kind"] == CreditAction.IMAGE_NANO_BANANA.value
    assert props["credits_cost"] == 4
    assert isinstance(props["duration_ms"], int) and props["duration_ms"] >= 0
    assert "prompt" not in props and gen.prompt not in map(str, props.values())


async def test_generation_failure_emits_failed_without_the_error_text():
    gen, tracker = _generation(), FakeTracker()
    await FinalizeGeneration(_GenRepo(gen), _Credits(), tracker).execute(
        gen.id, error="provider said: user prompt was 'a secret'"
    )
    assert tracker.calls == [
        (gen.user_id, "generation_failed", {"kind": CreditAction.IMAGE_NANO_BANANA.value})
    ]


async def test_generation_already_settled_emits_nothing():
    gen, tracker = _generation(status=GenerationStatus.CANCELED), FakeTracker()
    await FinalizeGeneration(_GenRepo(gen), _Credits(), tracker).execute(
        gen.id, file_path="org/x.png", mime_type="image/png"
    )
    assert tracker.calls == []


async def test_generation_without_reservation_still_emits():
    gen, tracker = _generation(reservation_id=None), FakeTracker()
    await FinalizeGeneration(_GenRepo(gen), _Credits(), tracker).execute(
        gen.id, file_path="org/x.png", mime_type="image/png"
    )
    assert tracker.names == ["generation_completed"]


class _FakeCredits:
    def __init__(self, *, already: bool = False) -> None:
        self.already = already

    async def already_granted(self, idempotency_key: str) -> bool:
        return self.already

    async def grant(self, org_id, amount, description, user_id=None, idempotency_key=None):
        pass


def _purchase(user_id) -> CreditPackPurchased:
    return CreditPackPurchased(
        org_id=uuid.uuid4(),
        pack_name="Growth",
        credits=500,
        session_id="cs_test_1",
        purchaser_email="buyer@example.com",
        user_id=user_id,
        pack="growth",
        amount_cents=5000,
    )


async def test_credit_pack_purchase_emits_once_and_never_the_email():
    tracker, user_id = FakeTracker(), uuid.uuid4()
    await SyncBillingEvent(credits=_FakeCredits(), analytics=tracker).execute(_purchase(user_id))
    assert tracker.calls == [
        (user_id, "credit_pack_purchased", {"pack": "growth", "credits": 500, "amount_cents": 5000})
    ]
    # Stripe redelivery: already granted -> no second event.
    redelivered = FakeTracker()
    await SyncBillingEvent(credits=_FakeCredits(already=True), analytics=redelivered).execute(
        _purchase(user_id)
    )
    assert redelivered.calls == []


class _MembershipRepo:
    def __init__(self, membership: CommunityMembership) -> None:
        self.membership = membership

    async def get_by_user(self, user_id):
        return self.membership if self.membership.user_id == user_id else None

    async def get_by_subscription_id(self, subscription_id):
        if self.membership.stripe_subscription_id == subscription_id:
            return self.membership
        return None


async def test_community_subscription_events_fire_on_tier_transitions_only():
    user_id = uuid.uuid4()
    membership = CommunityMembership(user_id=user_id)
    tracker = FakeTracker()
    applier = ApplyCommunitySubscriptionEvent(_MembershipRepo(membership), tracker)

    def sync(status):
        return applier.sync(
            subscription_id="sub_1",
            status=status,
            current_period_end=None,
            cancel_at_period_end=False,
            user_id=user_id,
        )

    # subscription.created outraces checkout.session.completed: one activation.
    await sync(SubscriptionStatus.ACTIVE)
    await applier.activate(user_id=user_id, stripe_customer_id="cus_1", subscription_id="sub_1")
    await applier.activate(user_id=user_id, stripe_customer_id="cus_1", subscription_id="sub_1")
    assert tracker.names == ["community_subscription_activated"]

    # past_due keeps premium -> not a cancellation.
    await sync(SubscriptionStatus.PAST_DUE)
    assert tracker.names == ["community_subscription_activated"]

    # canceled status, then subscription.deleted (and its redelivery): one cancel.
    await sync(SubscriptionStatus.CANCELED)
    await applier.end(subscription_id="sub_1")
    await applier.end(subscription_id="sub_1")
    assert tracker.names == [
        "community_subscription_activated",
        "community_subscription_canceled",
    ]
    assert {uid for uid, _, _ in tracker.calls} == {user_id}


# ── end to end: signed Stripe webhook -> activity_events ─────────────

WEBHOOK_SECRET = "whsec_analytics_test"  # noqa: S105 — test fixture, not a secret


def _signed_checkout_completed(
    org_id: str, *, session_id: str, user_id: str | None
) -> tuple[bytes, dict]:
    import json

    from tests.helpers import stripe_signature

    metadata = {"organization_id": org_id, "credit_pack": "growth"}
    if user_id is not None:
        metadata["user_id"] = user_id
    payload = json.dumps(
        {
            "id": "evt_analytics_1",
            "object": "event",
            "api_version": "2024-06-20",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "object": "checkout.session",
                    "mode": "payment",
                    "client_reference_id": org_id,
                    "metadata": metadata,
                    "customer_details": {"email": "buyer@example.com"},
                }
            },
        }
    ).encode()
    return payload, {"stripe-signature": stripe_signature(payload, WEBHOOK_SECRET)}


async def test_stripe_webhook_writes_one_purchase_event_for_the_buyer(client, db, monkeypatch):
    from app.core.config import settings
    from tests.helpers import create_org

    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    user, headers = await register_and_login(client)
    org = await create_org(client, headers)

    payload, sig = _signed_checkout_completed(org["id"], session_id="cs_a", user_id=user["id"])
    for _ in range(2):  # Stripe delivers at least once
        res = await client.post("/api/billing/webhook", content=payload, headers=sig)
        assert res.status_code == 200, res.text

    (row,) = await _rows(db)
    assert str(row["user_id"]) == user["id"]
    assert (row["event"], row["source"]) == ("credit_pack_purchased", "server")
    assert row["properties"]["pack"] == "growth"
    assert row["properties"]["credits"] > 0 and row["properties"]["amount_cents"] > 0
    assert "buyer@example.com" not in str(row["properties"])


async def test_stripe_webhook_without_or_with_garbage_buyer_still_grants(client, db, monkeypatch):
    """Sessions created before the user_id stamp (or with a mangled one) must
    grant credits exactly as before — just without an analytics row."""
    from app.core.config import settings
    from tests.helpers import create_org

    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    before = (await client.get(f"/api/orgs/{org['id']}/credits", headers=headers)).json()["balance"]

    for session_id, buyer in (("cs_legacy", None), ("cs_garbage", "not-a-uuid")):
        payload, sig = _signed_checkout_completed(org["id"], session_id=session_id, user_id=buyer)
        res = await client.post("/api/billing/webhook", content=payload, headers=sig)
        assert res.status_code == 200, res.text

    after = (await client.get(f"/api/orgs/{org['id']}/credits", headers=headers)).json()["balance"]
    assert after > before
    assert await _rows(db) == []
