"""Credits domain tests: the engine state machine (reserve/capture/release,
lazy expiry + allowance, grants/adjustments) exercised directly, plus the
HTTP wallet/history/action-cost endpoints.

Engine tests drive `build_credit_engine(db)` against the `db` fixture session.
That fixture hands back a plain session (no per-request transaction wrapper),
so each test owns its transactions: mutations run inside `async with db.begin():`
and the autocommit on block-exit makes the state visible to later HTTP requests
(which use their own session against the same test DB).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.domains.credits.application.facade import hold_credits
from app.domains.credits.domain import (
    ACTIONS,
    MONTHLY_ALLOWANCE_CREDITS,
    CreditAction,
    CreditReservation,
    CreditTransaction,
    InsufficientCredits,
    ReservationNotActive,
    ReservationNotFound,
    ReservationStatus,
    TransactionType,
    UnknownAction,
)
from app.domains.credits.infrastructure.repositories import (
    SqlAlchemyReservationRepository,
)
from app.domains.credits.interface.deps import build_credit_engine
from tests.helpers import auth_headers, create_org, register, register_and_login

LLM_COST = ACTIONS[CreditAction.LLM_CALL].cost
VEO_COST = ACTIONS[CreditAction.VIDEO_VEO].cost

# There is no free monthly allowance (MONTHLY_ALLOWANCE_CREDITS == 0) — tests
# that exercise the reserve/capture lifecycle seed the wallet explicitly.
SEED_CREDITS = 50


# ── helpers ──────────────────────────────────────────────────────────


async def _make_org(client) -> uuid.UUID:
    """Register the owner + an org via the API, returning the org UUID."""
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    return uuid.UUID(org["id"])


async def _seed(engine, db, org_id: uuid.UUID, amount: int = SEED_CREDITS) -> None:
    """Explicitly grant credits (replaces the retired free monthly allowance)."""
    async with db.begin():
        await engine.grant(org_id, amount, "Test seed")


async def _txns(db, org_id: uuid.UUID) -> list[CreditTransaction]:
    rows = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.organization_id == org_id)
        .order_by(CreditTransaction.created_at, CreditTransaction.id)
    )
    return list(rows.scalars())


def _types(txns) -> list[TransactionType]:
    return [t.type for t in txns]


# ── no free allowance on first touch ─────────────────────────────────


async def test_first_summary_grants_no_free_credits(client, db):
    # Regression: free orgs must start (and stay) at zero — validation is the
    # free tier; browsing requires purchased credits.
    assert MONTHLY_ALLOWANCE_CREDITS == 0

    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        wallet, pending = await engine.summary(org_id)

    assert wallet.balance == 0
    assert pending == []
    assert wallet.allowance_period == datetime.now(UTC).strftime("%Y-%m")

    assert await _txns(db, org_id) == []


async def test_repeated_touches_never_grant_free_credits(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        await engine.summary(org_id)
    async with db.begin():
        wallet, _ = await engine.summary(org_id)

    assert wallet.balance == 0
    grants = [t for t in await _txns(db, org_id) if t.type == TransactionType.GRANT]
    assert grants == []


# ── reserve / capture / release ──────────────────────────────────────


async def test_reserve_deducts_balance_and_opens_pending_hold(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL, reference="r1")

    assert res.status == ReservationStatus.PENDING
    assert res.amount == LLM_COST
    assert res.reference == "r1"

    async with db.begin():
        wallet, pending = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS - LLM_COST
    assert len(pending) == 1

    txns = await _txns(db, org_id)
    assert _types(txns) == [TransactionType.GRANT, TransactionType.HOLD]
    hold = txns[1]
    assert hold.amount == -LLM_COST  # signed: a hold debits available balance
    assert hold.action == CreditAction.LLM_CALL
    assert hold.reservation_id == res.id


async def test_capture_flips_state_and_leaves_balance_unchanged(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    async with db.begin():
        captured = await engine.capture(res.id)

    assert captured.status == ReservationStatus.CAPTURED
    assert captured.finalized_at is not None

    async with db.begin():
        wallet, pending = await engine.summary(org_id)
    # Balance was already debited at reserve time — capture only flips state.
    assert wallet.balance == SEED_CREDITS - LLM_COST
    assert pending == []

    # Capture writes no ledger entry on the happy path.
    assert _types(await _txns(db, org_id)) == [TransactionType.GRANT, TransactionType.HOLD]


async def test_release_refunds_and_restores_balance(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    async with db.begin():
        released = await engine.release(res.id, reason="provider failed")

    assert released.status == ReservationStatus.RELEASED

    async with db.begin():
        wallet, pending = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS  # fully restored
    assert pending == []

    txns = await _txns(db, org_id)
    assert _types(txns) == [TransactionType.GRANT, TransactionType.HOLD, TransactionType.RELEASE]
    assert txns[-1].amount == LLM_COST  # refund is positive
    assert txns[-1].description == "provider failed"


# ── hold_credits context manager ─────────────────────────────────────


async def test_hold_credits_captures_on_success(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        await engine.grant(org_id, SEED_CREDITS, "Test seed")
        async with hold_credits(
            engine, org_id=org_id, user_id=None, action=CreditAction.LLM_CALL
        ) as res:
            reservation_id = res.id

    async with db.begin():
        wallet, pending = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS - LLM_COST
    assert pending == []

    reservation = await db.get(CreditReservation, reservation_id)
    assert reservation.status == ReservationStatus.CAPTURED


async def test_hold_credits_releases_on_exception(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)

    class Boom(Exception):
        pass

    # Catch the failure INSIDE the transaction so it commits: an unhandled
    # exception would roll the whole request transaction back (reserve and
    # all); the facade's release matters when the caller handles the error
    # and the transaction still commits.
    reservation_id = None
    async with db.begin():
        try:
            async with hold_credits(
                engine, org_id=org_id, user_id=None, action=CreditAction.LLM_CALL
            ) as res:
                reservation_id = res.id
                raise Boom()
        except Boom:
            pass

    async with db.begin():
        wallet, pending = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS  # refunded
    assert pending == []

    reservation = await db.get(CreditReservation, reservation_id)
    assert reservation.status == ReservationStatus.RELEASED


# ── lazy stale-hold expiry ───────────────────────────────────────────


async def test_summary_lazily_expires_stale_holds(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)

    # Drag the hold's expiry into the past, directly on the row.
    async with db.begin():
        reservation = await db.get(CreditReservation, res.id)
        reservation.expires_at = datetime.now(UTC) - timedelta(minutes=5)

    async with db.begin():
        wallet, pending = await engine.summary(org_id)

    assert wallet.balance == SEED_CREDITS  # hold refunded
    assert pending == []

    reservation = await db.get(CreditReservation, res.id)
    assert reservation.status == ReservationStatus.EXPIRED

    txns = await _txns(db, org_id)
    assert TransactionType.EXPIRE in _types(txns)
    expire_tx = next(t for t in txns if t.type == TransactionType.EXPIRE)
    assert expire_tx.amount == LLM_COST  # refund


async def test_late_capture_of_expired_reservation_recharges_as_adjustment(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    # Seed exactly one VEO hold's worth so a re-charge takes us negative.
    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.VIDEO_VEO)

    async with db.begin():
        reservation = await db.get(CreditReservation, res.id)
        reservation.expires_at = datetime.now(UTC) - timedelta(hours=3)

    # Settle so the hold expires and the credits are refunded.
    async with db.begin():
        wallet, _ = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS
    refunded = await db.get(CreditReservation, res.id)
    assert refunded.status == ReservationStatus.EXPIRED

    # The result arrives late: the service WAS delivered, so re-charge it.
    async with db.begin():
        captured = await engine.capture(res.id)
    assert captured.status == ReservationStatus.CAPTURED

    async with db.begin():
        wallet, _ = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS - VEO_COST  # 50 - 50 == 0 here

    txns = await _txns(db, org_id)
    adjustments = [t for t in txns if t.type == TransactionType.ADJUSTMENT]
    assert len(adjustments) == 1
    assert adjustments[0].amount == -VEO_COST


async def test_late_capture_can_drive_balance_negative(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)  # 50 -> 49

    # The hold expires and is refunded (49 -> 50)...
    async with db.begin():
        reservation = await db.get(CreditReservation, res.id)
        reservation.expires_at = datetime.now(UTC) - timedelta(minutes=30)
    async with db.begin():
        await engine.summary(org_id)

    # ...and the refund is spent elsewhere before the late result arrives.
    async with db.begin():
        await engine.reserve(org_id, None, CreditAction.VIDEO_VEO)  # 50 -> 0

    async with db.begin():
        await engine.capture(res.id)  # late re-charge: the service WAS delivered

    async with db.begin():
        wallet, _ = await engine.summary(org_id)
    assert wallet.balance == -LLM_COST  # 0 - 1: the late charge overdraws


# ── grants & adjustments ─────────────────────────────────────────────


async def test_grant_adds_credits(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        await engine.summary(org_id)
    async with db.begin():
        wallet = await engine.grant(org_id, 100, "Promo grant")

    assert wallet.balance == 100

    txns = await _txns(db, org_id)
    grants = [t for t in txns if t.type == TransactionType.GRANT]
    # No free allowance — the explicit grant is the only one.
    assert len(grants) == 1
    assert grants[-1].amount == 100
    assert grants[-1].description == "Promo grant"


async def test_grant_with_idempotency_key_is_safe_on_redelivery(client, db):
    """A webhook redelivery (same idempotency_key) grants exactly once even if
    the up-front already_granted check is skipped — the post-lock recheck and
    the unique index together keep the wallet from being double-credited."""
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        await engine.summary(org_id)
    async with db.begin():
        await engine.grant(org_id, 500, "Credit pack", idempotency_key="cs_test_dup")
    async with db.begin():
        # Same key again: must no-op, not raise, not double-credit.
        wallet = await engine.grant(org_id, 500, "Credit pack", idempotency_key="cs_test_dup")

    assert wallet.balance == 500  # granted once
    pack_grants = [
        t
        for t in await _txns(db, org_id)
        if t.type == TransactionType.GRANT and t.idempotency_key == "cs_test_dup"
    ]
    assert len(pack_grants) == 1


async def test_grant_tolerates_preexisting_idempotency_key(client, db):
    """The unique-index backstop: a ledger row with the key already exists, so
    a fresh grant for the same key rolls back its insert (savepoint) and the
    wallet increment, leaving the balance untouched — no IntegrityError."""
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        await engine.summary(org_id)
    async with db.begin():
        await engine.grant(org_id, 500, "Credit pack", idempotency_key="cs_seed")

    balance_before = await _make_engine_summary(engine, db, org_id)

    async with db.begin():
        wallet = await engine.grant(org_id, 500, "Credit pack", idempotency_key="cs_seed")

    assert wallet.balance == balance_before  # no second credit
    keyed = [t for t in await _txns(db, org_id) if t.idempotency_key == "cs_seed"]
    assert len(keyed) == 1


async def _make_engine_summary(engine, db, org_id) -> int:
    async with db.begin():
        wallet, _ = await engine.summary(org_id)
    return wallet.balance


async def test_adjust_can_remove_credits_and_go_negative(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    async with db.begin():
        await engine.summary(org_id)
    async with db.begin():
        wallet = await engine.adjust(org_id, -10, "Clawback")

    assert wallet.balance == -10
    txns = await _txns(db, org_id)
    adj = [t for t in txns if t.type == TransactionType.ADJUSTMENT]
    assert len(adj) == 1
    assert adj[0].amount == -10


# ── sweep / settle (use-case level) ──────────────────────────────────
#
# `worker.sweep_stale_reservations()` opens its own `SessionLocal` sessions,
# and `SessionLocal` (app.core.database) is bound to `settings.database_url`
# — the dev DB, NOT the `app_test` DB the conftest wires the app to (conftest
# only overrides `get_db`). So the worker would never see rows we write in the
# test DB. We therefore exercise the sweep's actual logic at the use-case
# level: repo.list_orgs_with_stale_pending + engine.settle, both on the test
# session. (worker.py itself is left untested — see the test-suite summary.)


async def test_settle_refunds_dormant_orgs_stale_holds(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)

    async with db.begin():
        reservation = await db.get(CreditReservation, res.id)
        reservation.expires_at = datetime.now(UTC) - timedelta(minutes=20)

    # This is exactly what sweep_stale_reservations() does, minus its own
    # SessionLocal sessions: find stale orgs, then settle each one. (The read
    # runs in its own transaction — a bare execute would autobegin one and
    # collide with the explicit db.begin() below.)
    repo = SqlAlchemyReservationRepository(db)
    async with db.begin():
        stale_orgs = await repo.list_orgs_with_stale_pending(datetime.now(UTC))
    assert org_id in stale_orgs

    async with db.begin():
        settled = await engine.settle(org_id)
    assert settled.balance == SEED_CREDITS  # hold refunded

    reservation = await db.get(CreditReservation, res.id)
    assert reservation.status == ReservationStatus.EXPIRED

    # Once settled, the org no longer appears as stale (idempotent).
    stale_orgs = await repo.list_orgs_with_stale_pending(datetime.now(UTC))
    assert org_id not in stale_orgs


async def test_list_orgs_with_stale_pending_ignores_fresh_holds(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        await engine.reserve(org_id, None, CreditAction.VIDEO_VEO)  # 2h TTL, fresh

    repo = SqlAlchemyReservationRepository(db)
    stale = await repo.list_orgs_with_stale_pending(datetime.now(UTC))
    assert org_id not in stale


# ── error paths ──────────────────────────────────────────────────────


async def test_reserve_with_insufficient_credits_raises(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    # A fresh org has zero credits (no free allowance) — any reserve fails.
    async with db.begin():
        await engine.summary(org_id)

    raised = False
    try:
        async with db.begin():
            await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    except InsufficientCredits:
        raised = True
    assert raised


async def test_reserve_unknown_action_raises(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    # An action with no entry in the ACTIONS catalog is rejected before any
    # wallet touch. Build a throwaway enum-shaped value the lookup won't find.
    class _Bogus(str):
        pass

    bogus = _Bogus("not_a_real_action")

    async with db.begin():
        await engine.summary(org_id)

    raised = False
    try:
        async with db.begin():
            await engine.reserve(org_id, None, bogus)  # type: ignore[arg-type]
    except UnknownAction:
        raised = True
    assert raised


async def test_capture_already_captured_raises_not_active(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    async with db.begin():
        await engine.capture(res.id)

    raised = False
    try:
        async with db.begin():
            await engine.capture(res.id)
    except ReservationNotActive:
        raised = True
    assert raised


async def test_release_after_capture_raises_not_active(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    async with db.begin():
        await engine.capture(res.id)

    raised = False
    try:
        async with db.begin():
            await engine.release(res.id)
    except ReservationNotActive:
        raised = True
    assert raised


async def test_release_twice_is_idempotent(client, db):
    org_id = await _make_org(client)
    engine = build_credit_engine(db)

    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    async with db.begin():
        await engine.release(res.id)
    # A second release must not raise and must not double-refund.
    async with db.begin():
        again = await engine.release(res.id)
    assert again.status == ReservationStatus.RELEASED

    async with db.begin():
        wallet, _ = await engine.summary(org_id)
    assert wallet.balance == SEED_CREDITS  # refunded exactly once

    releases = [t for t in await _txns(db, org_id) if t.type == TransactionType.RELEASE]
    assert len(releases) == 1


async def test_capture_missing_reservation_raises_not_found(client, db):
    engine = build_credit_engine(db)
    raised = False
    try:
        async with db.begin():
            await engine.capture(uuid.uuid4())
    except ReservationNotFound:
        raised = True
    assert raised


# ── HTTP: action costs ───────────────────────────────────────────────


async def test_action_costs_endpoint_is_public(client):
    # No auth header — the catalog is public.
    res = await client.get("/api/credits/actions")
    assert res.status_code == 200, res.text
    body = res.json()
    by_action = {row["action"]: row for row in body}
    assert by_action[CreditAction.LLM_CALL.value]["cost"] == LLM_COST
    assert by_action[CreditAction.VIDEO_VEO.value]["cost"] == VEO_COST
    assert set(by_action) == {a.value for a in CreditAction}


# ── HTTP: wallet ─────────────────────────────────────────────────────


async def test_get_wallet_returns_balance_and_pending(client, db):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    org_id = uuid.UUID(org["id"])

    # Seed, then open a hold via the engine so the wallet shows a reservation.
    engine = build_credit_engine(db)
    await _seed(engine, db, org_id)
    async with db.begin():
        await engine.reserve(org_id, None, CreditAction.LLM_CALL)

    res = await client.get(f"/api/orgs/{org['id']}/credits", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["balance"] == SEED_CREDITS - LLM_COST
    assert body["reserved"] == LLM_COST
    assert body["monthly_allowance"] == 0
    assert len(body["pending_holds"]) == 1
    assert body["pending_holds"][0]["action"] == CreditAction.LLM_CALL.value
    assert body["pending_holds"][0]["status"] == ReservationStatus.PENDING.value


async def test_get_wallet_first_touch_is_zero_balance(client):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)

    res = await client.get(f"/api/orgs/{org['id']}/credits", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["balance"] == 0
    assert body["reserved"] == 0
    assert body["pending_holds"] == []


async def test_get_wallet_non_member_gets_404(client):
    # Owner creates the org.
    _, owner_headers = await register_and_login(client, email="owner@example.com")
    org = await create_org(client, owner_headers)

    # A different, unaffiliated user must not learn the org exists.
    await register(client, email="outsider@example.com")
    res = await client.post(
        "/api/auth/login", json={"email": "outsider@example.com", "password": "correct-horse9"}
    )
    outsider_headers = auth_headers(res.json()["access_token"])

    res = await client.get(f"/api/orgs/{org['id']}/credits", headers=outsider_headers)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_PERM_002"


# ── HTTP: history pagination ─────────────────────────────────────────


async def test_history_returns_ledger_entries(client, db):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    org_id = uuid.UUID(org["id"])

    engine = build_credit_engine(db)
    await _seed(engine, db, org_id)
    async with db.begin():
        res = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    async with db.begin():
        await engine.release(res.id)

    res = await client.get(f"/api/orgs/{org['id']}/credits/history", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    # GRANT (test seed) + HOLD + RELEASE.
    assert body["total"] == 3
    types = [item["type"] for item in body["items"]]
    assert TransactionType.RELEASE.value in types
    assert TransactionType.HOLD.value in types
    assert TransactionType.GRANT.value in types


async def test_history_paginates_with_limit_and_offset(client, db):
    _, headers = await register_and_login(client)
    org = await create_org(client, headers)
    org_id = uuid.UUID(org["id"])

    engine = build_credit_engine(db)
    async with db.begin():
        await engine.grant(org_id, 1, "g1")
    async with db.begin():
        await engine.grant(org_id, 2, "g2")
    async with db.begin():
        await engine.grant(org_id, 3, "g3")
    # Total ledger entries: g1 + g2 + g3 == 3 (no free allowance grant).

    first = await client.get(
        f"/api/orgs/{org['id']}/credits/history?limit=1&offset=0", headers=headers
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["total"] == 3
    assert len(first_body["items"]) == 1

    second = await client.get(
        f"/api/orgs/{org['id']}/credits/history?limit=1&offset=1", headers=headers
    )
    assert len(second.json()["items"]) == 1
    # Newest-first ordering: page 2 is a different row than page 1.
    assert second.json()["items"][0]["id"] != first_body["items"][0]["id"]


async def test_history_non_member_gets_404(client):
    _, owner_headers = await register_and_login(client, email="owner@example.com")
    org = await create_org(client, owner_headers)

    await register(client, email="outsider@example.com")
    res = await client.post(
        "/api/auth/login", json={"email": "outsider@example.com", "password": "correct-horse9"}
    )
    outsider_headers = auth_headers(res.json()["access_token"])

    res = await client.get(f"/api/orgs/{org['id']}/credits/history", headers=outsider_headers)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_PERM_002"
