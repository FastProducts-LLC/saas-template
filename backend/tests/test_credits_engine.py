"""Credit engine unit tests: reserve/capture/release, allowance, expiry, grants.

Pure unit tests — the engine is constructed directly over in-memory fakes of
its ports; no database, no HTTP client, no conftest fixtures used.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.domains.credits.application.use_cases import CreditEngine
from app.domains.credits.domain import (
    ACTIONS,
    CreditAction,
    CreditReservation,
    CreditWallet,
    InsufficientCredits,
    MemberCreditLimit,
    MemberCreditLimitExceeded,
    ReservationNotActive,
    ReservationStatus,
    TransactionType,
    UnknownAction,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _period() -> str:
    return _now().strftime("%Y-%m")


# -- reusable in-memory fakes -------------------------------------------------


class FakeWalletRepository:
    def __init__(self) -> None:
        self.wallets: dict[uuid.UUID, CreditWallet] = {}

    async def get_for_org_locked(self, org_id: uuid.UUID) -> CreditWallet | None:
        return self.wallets.get(org_id)

    async def add_if_absent(self, wallet: CreditWallet) -> bool:
        if wallet.organization_id in self.wallets:
            return False
        self.wallets[wallet.organization_id] = wallet
        return True


class FakeReservationRepository:
    def __init__(self) -> None:
        self.reservations: dict[uuid.UUID, CreditReservation] = {}

    async def get(self, reservation_id: uuid.UUID) -> CreditReservation | None:
        return self.reservations.get(reservation_id)

    async def get_locked(self, reservation_id: uuid.UUID) -> CreditReservation | None:
        return self.reservations.get(reservation_id)

    async def list_stale_pending(self, org_id: uuid.UUID, now: datetime) -> list[CreditReservation]:
        return [
            r
            for r in self.reservations.values()
            if r.organization_id == org_id
            and r.status == ReservationStatus.PENDING
            and r.expires_at <= now
        ]

    async def list_orgs_with_stale_pending(
        self, now: datetime, limit: int = 500
    ) -> list[uuid.UUID]:
        seen: list[uuid.UUID] = []
        for r in self.reservations.values():
            if (
                r.status == ReservationStatus.PENDING
                and r.expires_at <= now
                and r.organization_id not in seen
            ):
                seen.append(r.organization_id)
        return seen[:limit]

    async def list_pending(self, org_id: uuid.UUID) -> list[CreditReservation]:
        return [
            r
            for r in self.reservations.values()
            if r.organization_id == org_id and r.status == ReservationStatus.PENDING
        ]

    async def add(self, reservation: CreditReservation) -> None:
        self.reservations[reservation.id] = reservation

    async def sum_active_for_user(
        self, org_id: uuid.UUID, user_id: uuid.UUID, since: datetime
    ) -> int:
        return sum(
            r.amount
            for r in self.reservations.values()
            if r.organization_id == org_id
            and r.user_id == user_id
            and r.status in (ReservationStatus.PENDING, ReservationStatus.CAPTURED)
            and r.created_at >= since
        )


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.entries: list = []

    def add(self, tx) -> None:
        self.entries.append(tx)

    async def add_idempotent(self, tx) -> bool:
        """Emulates the partial unique index on idempotency_key: a second row
        with the same non-null key is rejected (returns False)."""
        if tx.idempotency_key is not None and any(
            e.idempotency_key == tx.idempotency_key for e in self.entries
        ):
            return False
        self.entries.append(tx)
        return True

    async def exists_with_idempotency_key(self, key: str) -> bool:
        return any(tx.idempotency_key == key for tx in self.entries)

    async def list_for_org(self, org_id: uuid.UUID, limit: int, offset: int) -> list:
        rows = [tx for tx in self.entries if tx.organization_id == org_id]
        return rows[offset : offset + limit]

    async def count_for_org(self, org_id: uuid.UUID) -> int:
        return sum(1 for tx in self.entries if tx.organization_id == org_id)

    def of_type(self, type: TransactionType) -> list:
        return [tx for tx in self.entries if tx.type == type]


class FakeMemberLimitRepository:
    def __init__(self) -> None:
        self.limits: dict[tuple[uuid.UUID, uuid.UUID], MemberCreditLimit] = {}

    async def get(self, org_id: uuid.UUID, user_id: uuid.UUID) -> MemberCreditLimit | None:
        return self.limits.get((org_id, user_id))

    async def add(self, limit: MemberCreditLimit) -> None:
        self.limits[(limit.organization_id, limit.user_id)] = limit

    async def remove(self, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return self.limits.pop((org_id, user_id), None) is not None

    async def list_with_usage(self, org_id: uuid.UUID, since: datetime) -> list:
        return [(lim, None, 0) for (o, _), lim in self.limits.items() if o == org_id]


class FakeNotifier:
    def __init__(self, *, raises: bool = False) -> None:
        self.calls: list[dict] = []
        self.raises = raises

    async def notify_low_balance(
        self, *, balance: int, allowance: int, recipient_emails: list[str]
    ) -> None:
        self.calls.append(
            {"balance": balance, "allowance": allowance, "recipient_emails": recipient_emails}
        )
        if self.raises:
            raise RuntimeError("mail down")


class FakeOwnerEmails:
    def __init__(self, emails: list[str] | None = None) -> None:
        self.emails = emails if emails is not None else ["owner@example.com"]

    async def owner_emails(self, org_id: uuid.UUID) -> list[str]:
        return list(self.emails)


def build_engine(
    *,
    notifier: FakeNotifier | None = None,
    owners: FakeOwnerEmails | None = None,
    ledger: FakeLedgerRepository | None = None,
    limits: FakeMemberLimitRepository | None = None,
) -> tuple[CreditEngine, FakeWalletRepository, FakeReservationRepository, FakeLedgerRepository]:
    wallets = FakeWalletRepository()
    reservations = FakeReservationRepository()
    ledger = ledger if ledger is not None else FakeLedgerRepository()
    engine = CreditEngine(
        wallets,
        reservations,
        ledger,
        notifier=notifier,
        owners=owners,
        limits=limits,
    )
    return engine, wallets, reservations, ledger


def seed_wallet(wallets: FakeWalletRepository, org_id: uuid.UUID, balance: int) -> CreditWallet:
    """Seed a wallet already in the current period so the allowance grant
    doesn't run and disturb the balance we want to test."""
    wallet = CreditWallet(organization_id=org_id, balance=balance, allowance_period=_period())
    wallets.wallets[org_id] = wallet
    return wallet


# -- tests --------------------------------------------------------------------


async def test_reserve_happy_path():
    org_id = uuid.uuid4()
    engine, wallets, reservations, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    cost = ACTIONS[CreditAction.LLM_CALL].cost
    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)

    assert wallets.wallets[org_id].balance == 10 - cost
    assert reservation.status == ReservationStatus.PENDING
    assert reservation.amount == cost

    holds = ledger.of_type(TransactionType.HOLD)
    assert len(holds) == 1
    assert holds[0].amount == -cost
    assert holds[0].balance_after == 10 - cost
    assert holds[0].reservation_id == reservation.id


async def test_reserve_insufficient_balance_writes_no_reservation():
    org_id = uuid.uuid4()
    engine, wallets, reservations, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=0)

    try:
        await engine.reserve(org_id, None, CreditAction.IMAGE_GPT)
        raise AssertionError("expected InsufficientCredits")
    except InsufficientCredits:
        pass

    assert reservations.reservations == {}
    assert ledger.of_type(TransactionType.HOLD) == []


async def test_reserve_unknown_action_raises():
    org_id = uuid.uuid4()
    engine, wallets, _, _ = build_engine()
    seed_wallet(wallets, org_id, balance=100)

    class FakeAction:
        value = "not_a_real_action"

    try:
        await engine.reserve(org_id, None, FakeAction())
        raise AssertionError("expected UnknownAction")
    except UnknownAction:
        pass


async def test_first_touch_grants_no_free_allowance():
    # MONTHLY_ALLOWANCE_CREDITS is 0 — identity checks are the free tier;
    # browsing credits come only from purchased packs.
    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine()

    # Fresh wallet, no allowance_period -> first touch stamps the period
    # but grants nothing.
    wallet = await engine.settle(org_id)
    assert wallet.balance == 0
    assert wallet.allowance_period == _period()
    assert ledger.of_type(TransactionType.GRANT) == []

    # Second touch in the same period changes nothing.
    wallet = await engine.settle(org_id)
    assert wallet.balance == 0
    assert ledger.of_type(TransactionType.GRANT) == []


async def test_monthly_allowance_granted_once_per_period(monkeypatch):
    # Mechanism test: with a nonzero allowance configured, the grant fires
    # exactly once per period. Patched because the product default is 0.
    monkeypatch.setattr("app.domains.credits.application.use_cases.MONTHLY_ALLOWANCE_CREDITS", 50)
    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine()

    wallet = await engine.settle(org_id)
    assert wallet.balance == 50
    assert wallet.allowance_period == _period()
    grants = ledger.of_type(TransactionType.GRANT)
    assert len(grants) == 1
    assert grants[0].amount == 50

    # Second touch in the same period grants nothing more.
    wallet = await engine.settle(org_id)
    assert wallet.balance == 50
    assert len(ledger.of_type(TransactionType.GRANT)) == 1


async def test_capture_pending_no_balance_change():
    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    balance_after_hold = wallets.wallets[org_id].balance
    ledger_len = len(ledger.entries)

    captured = await engine.capture(reservation.id)
    assert captured.status == ReservationStatus.CAPTURED
    assert wallets.wallets[org_id].balance == balance_after_hold
    assert len(ledger.entries) == ledger_len  # no extra ledger entry


async def test_release_refunds_and_is_idempotent():
    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    cost = ACTIONS[CreditAction.LLM_CALL].cost
    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    assert wallets.wallets[org_id].balance == 10 - cost

    released = await engine.release(reservation.id)
    assert released.status == ReservationStatus.RELEASED
    assert wallets.wallets[org_id].balance == 10
    releases = ledger.of_type(TransactionType.RELEASE)
    assert len(releases) == 1
    assert releases[0].amount == cost

    # Releasing again is a no-op (idempotent) — balance and ledger unchanged.
    await engine.release(reservation.id)
    assert wallets.wallets[org_id].balance == 10
    assert len(ledger.of_type(TransactionType.RELEASE)) == 1


async def test_release_captured_raises_not_active():
    org_id = uuid.uuid4()
    engine, wallets, _, _ = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    await engine.capture(reservation.id)

    try:
        await engine.release(reservation.id)
        raise AssertionError("expected ReservationNotActive")
    except ReservationNotActive:
        pass


async def test_pending_expires_and_refunds_on_next_touch():
    org_id = uuid.uuid4()
    engine, wallets, reservations, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    cost = ACTIONS[CreditAction.LLM_CALL].cost
    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    assert wallets.wallets[org_id].balance == 10 - cost

    # Force the hold to be already past its TTL.
    reservation.expires_at = _now() - timedelta(minutes=1)

    wallet = await engine.settle(org_id)
    assert reservation.status == ReservationStatus.EXPIRED
    assert wallet.balance == 10  # refunded
    expires = ledger.of_type(TransactionType.EXPIRE)
    assert len(expires) == 1
    assert expires[0].amount == cost


async def test_late_capture_after_expiry_recharges():
    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=1)

    cost = ACTIONS[CreditAction.LLM_CALL].cost
    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    assert wallets.wallets[org_id].balance == 1 - cost  # 0

    # Expire + refund it via a touch.
    reservation.expires_at = _now() - timedelta(minutes=1)
    await engine.settle(org_id)
    assert reservation.status == ReservationStatus.EXPIRED
    assert wallets.wallets[org_id].balance == 1

    # Late capture re-charges as an ADJUSTMENT; balance may go negative.
    captured = await engine.capture(reservation.id)
    assert captured.status == ReservationStatus.CAPTURED
    assert wallets.wallets[org_id].balance == 1 - cost
    adjustments = ledger.of_type(TransactionType.ADJUSTMENT)
    assert len(adjustments) == 1
    assert adjustments[0].amount == -cost


async def test_grant_idempotency_key_and_already_granted():
    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=0)

    key = "stripe_session_abc"
    assert await engine.already_granted(key) is False

    await engine.grant(org_id, 500, "Credit pack", idempotency_key=key)
    grants = ledger.of_type(TransactionType.GRANT)
    assert len(grants) == 1
    assert grants[0].idempotency_key == key
    assert wallets.wallets[org_id].balance == 500

    assert await engine.already_granted(key) is True

    # Redelivery with the same key is a no-op: no second grant, no balance change.
    await engine.grant(org_id, 500, "Credit pack", idempotency_key=key)
    assert len(ledger.of_type(TransactionType.GRANT)) == 1
    assert wallets.wallets[org_id].balance == 500


async def test_grant_unique_index_backstop_undoes_wallet_increment():
    """If a racing grant commits between the already_granted check and the
    insert (read skew), the unique index rejects the row — the engine must
    then undo the in-memory wallet increment."""

    class ReadSkewLedger(FakeLedgerRepository):
        async def exists_with_idempotency_key(self, key: str) -> bool:
            return False  # simulate the check missing a concurrent commit

    org_id = uuid.uuid4()
    engine, wallets, _, ledger = build_engine(ledger=ReadSkewLedger())
    seed_wallet(wallets, org_id, balance=0)

    await engine.grant(org_id, 500, "First delivery", idempotency_key="cs_race")
    assert wallets.wallets[org_id].balance == 500
    # Second delivery: already_granted lies (False), add_idempotent rejects.
    await engine.grant(org_id, 500, "Redelivery", idempotency_key="cs_race")
    assert len(ledger.of_type(TransactionType.GRANT)) == 1
    assert wallets.wallets[org_id].balance == 500  # increment rolled back


async def test_low_balance_notify_fires_once_and_debounces(monkeypatch):
    # The heads-up is keyed off the allowance and disabled while it is 0 —
    # patch a nonzero allowance to exercise the crossing/debounce mechanism.
    monkeypatch.setattr("app.domains.credits.application.use_cases.MONTHLY_ALLOWANCE_CREDITS", 50)
    org_id = uuid.uuid4()
    notifier = FakeNotifier()
    owners = FakeOwnerEmails()
    engine, wallets, _, _ = build_engine(notifier=notifier, owners=owners)
    # allowance 50, fraction 0.2 -> threshold 10. Start at 11 (above threshold).
    wallet = seed_wallet(wallets, org_id, balance=11)

    # 11 -> 10 -> ... each LLM_CALL costs 1. Crossing happens at 11 -> 10.
    await engine.reserve(org_id, None, CreditAction.LLM_CALL)  # 11 -> 10 (crosses)
    assert len(notifier.calls) == 1
    assert notifier.calls[0]["balance"] == 10
    assert notifier.calls[0]["allowance"] == 50
    assert wallet.low_balance_notified_period == _period()

    # Further reserves in the same period must not re-notify (debounce).
    await engine.reserve(org_id, None, CreditAction.LLM_CALL)  # 10 -> 9
    await engine.reserve(org_id, None, CreditAction.LLM_CALL)  # 9 -> 8
    assert len(notifier.calls) == 1


async def test_low_balance_notify_resets_flag_on_new_period():
    org_id = uuid.uuid4()
    notifier = FakeNotifier()
    engine, wallets, _, _ = build_engine(notifier=notifier, owners=FakeOwnerEmails())
    wallet = seed_wallet(wallets, org_id, balance=11)
    # Pretend we already notified, but in a stale period.
    wallet.low_balance_notified_period = "1999-01"
    wallet.allowance_period = "1999-01"  # forces a fresh allowance this period

    # A new period: _apply_monthly_allowance resets low_balance_notified_period.
    await engine.settle(org_id)
    assert wallet.low_balance_notified_period is None
    assert wallet.allowance_period == _period()


async def test_low_balance_notifier_raising_does_not_break_reserve(monkeypatch):
    monkeypatch.setattr("app.domains.credits.application.use_cases.MONTHLY_ALLOWANCE_CREDITS", 50)
    org_id = uuid.uuid4()
    notifier = FakeNotifier(raises=True)
    engine, wallets, _, _ = build_engine(notifier=notifier, owners=FakeOwnerEmails())
    seed_wallet(wallets, org_id, balance=11)

    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL)
    # Notifier was invoked (and raised), but reserve still succeeded.
    assert len(notifier.calls) == 1
    assert reservation.status == ReservationStatus.PENDING
    assert wallets.wallets[org_id].balance == 10


# -- actor attribution (api_key_id) --------------------------------------------


async def test_reserve_stamps_api_key_on_reservation_and_hold():
    org_id, key_id = uuid.uuid4(), uuid.uuid4()
    engine, wallets, reservations, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL, api_key_id=key_id)

    assert reservation.user_id is None
    assert reservation.api_key_id == key_id
    holds = ledger.of_type(TransactionType.HOLD)
    assert holds[0].api_key_id == key_id
    assert holds[0].user_id is None


async def test_release_and_expiry_propagate_api_key_id():
    org_id, key_id = uuid.uuid4(), uuid.uuid4()
    engine, wallets, reservations, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    released = await engine.reserve(org_id, None, CreditAction.LLM_CALL, api_key_id=key_id)
    await engine.release(released.id)
    assert ledger.of_type(TransactionType.RELEASE)[0].api_key_id == key_id

    expired = await engine.reserve(org_id, None, CreditAction.LLM_CALL, api_key_id=key_id)
    expired.expires_at = _now() - timedelta(minutes=1)
    await engine.settle(org_id)
    assert ledger.of_type(TransactionType.EXPIRE)[0].api_key_id == key_id


async def test_late_capture_adjustment_propagates_api_key_id():
    org_id, key_id = uuid.uuid4(), uuid.uuid4()
    engine, wallets, reservations, ledger = build_engine()
    seed_wallet(wallets, org_id, balance=10)

    reservation = await engine.reserve(org_id, None, CreditAction.LLM_CALL, api_key_id=key_id)
    reservation.expire()  # hold expired before the result arrived
    await engine.capture(reservation.id)

    adjustments = ledger.of_type(TransactionType.ADJUSTMENT)
    assert len(adjustments) == 1
    assert adjustments[0].api_key_id == key_id


# -- per-member monthly limits --------------------------------------------------


def _seed_limit(
    limits: FakeMemberLimitRepository, org_id: uuid.UUID, user_id: uuid.UUID, cap: int
) -> None:
    limits.limits[(org_id, user_id)] = MemberCreditLimit(
        organization_id=org_id, user_id=user_id, monthly_limit=cap
    )


async def test_no_limit_row_means_unlimited():
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    engine, wallets, _, _ = build_engine(limits=FakeMemberLimitRepository())
    seed_wallet(wallets, org_id, balance=1000)

    for _ in range(20):
        await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
    assert wallets.wallets[org_id].balance == 980


async def test_limit_crossing_raises_and_writes_nothing():
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    limits = FakeMemberLimitRepository()
    _seed_limit(limits, org_id, user_id, cap=8)
    engine, wallets, reservations, ledger = build_engine(limits=limits)
    seed_wallet(wallets, org_id, balance=100)

    # IMAGE_NANO_BANANA costs 5: first passes (5/8), second would cross (10 > 8).
    await engine.reserve(org_id, user_id, CreditAction.IMAGE_NANO_BANANA)
    try:
        await engine.reserve(org_id, user_id, CreditAction.IMAGE_NANO_BANANA)
        raise AssertionError("expected MemberCreditLimitExceeded")
    except MemberCreditLimitExceeded:
        pass

    assert len(reservations.reservations) == 1
    assert len(ledger.of_type(TransactionType.HOLD)) == 1
    assert wallets.wallets[org_id].balance == 95  # only the first hold deducted


async def test_exact_boundary_passes_one_more_fails():
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    limits = FakeMemberLimitRepository()
    _seed_limit(limits, org_id, user_id, cap=2)
    engine, wallets, _, _ = build_engine(limits=limits)
    seed_wallet(wallets, org_id, balance=100)

    await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)  # 1/2
    await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)  # 2/2 — exact cap ok
    try:
        await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
        raise AssertionError("expected MemberCreditLimitExceeded")
    except MemberCreditLimitExceeded:
        pass


async def test_released_and_expired_holds_free_limit_headroom():
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    limits = FakeMemberLimitRepository()
    _seed_limit(limits, org_id, user_id, cap=1)
    engine, wallets, _, _ = build_engine(limits=limits)
    seed_wallet(wallets, org_id, balance=100)

    first = await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
    await engine.release(first.id)
    # Released hold no longer counts — the next reserve fits again.
    second = await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
    assert second.status == ReservationStatus.PENDING

    # Captured holds DO keep counting.
    await engine.capture(second.id)
    try:
        await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
        raise AssertionError("expected MemberCreditLimitExceeded")
    except MemberCreditLimitExceeded:
        pass


async def test_api_key_charges_ignore_member_limits():
    org_id, user_id, key_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    limits = FakeMemberLimitRepository()
    _seed_limit(limits, org_id, user_id, cap=1)
    engine, wallets, _, _ = build_engine(limits=limits)
    seed_wallet(wallets, org_id, balance=100)

    # user_id=None (API key) → limit machinery never consulted.
    for _ in range(5):
        await engine.reserve(org_id, None, CreditAction.LLM_CALL, api_key_id=key_id)
    assert wallets.wallets[org_id].balance == 95


async def test_prior_month_usage_excluded_from_limit():
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    limits = FakeMemberLimitRepository()
    _seed_limit(limits, org_id, user_id, cap=2)
    engine, wallets, reservations, _ = build_engine(limits=limits)
    seed_wallet(wallets, org_id, balance=100)

    first = await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
    await engine.capture(first.id)
    second = await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
    await engine.capture(second.id)

    # Backdate both captures to last month — headroom returns.
    for r in reservations.reservations.values():
        r.created_at = _now() - timedelta(days=40)

    third = await engine.reserve(org_id, user_id, CreditAction.LLM_CALL)
    assert third.status == ReservationStatus.PENDING
