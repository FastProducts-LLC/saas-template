"""LLM completion unit tests over a REAL credit engine.

The two-phase flow (StartLlmCall reserves + persists a pending call;
FinalizeLlmCall settles the hold) is wired to a real CreditEngine running on
in-memory credit-port fakes, so hold/capture/release semantics are actually
exercised. No database, no HTTP client, no conftest fixtures used.
"""

import uuid
from datetime import UTC, datetime

from app.domains.credits.application.use_cases import CreditEngine
from app.domains.credits.domain import (
    CreditReservation,
    CreditWallet,
    ReservationStatus,
    TransactionType,
)
from app.domains.llm.application.use_cases import FinalizeLlmCall, StartLlmCall
from app.domains.llm.domain.entities import (
    RESPONSE_PREVIEW_CHARS,
    LlmCall,
    LlmCallStatus,
    LlmProvider,
    LlmResult,
)
from app.domains.llm.domain.errors import LlmProviderNotConfigured


def _period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


# -- in-memory credit-port fakes (self-contained copy) ------------------------


class FakeWalletRepository:
    def __init__(self) -> None:
        self.wallets: dict[uuid.UUID, CreditWallet] = {}

    async def get_for_org_locked(self, org_id):
        return self.wallets.get(org_id)

    async def add_if_absent(self, wallet) -> bool:
        if wallet.organization_id in self.wallets:
            return False
        self.wallets[wallet.organization_id] = wallet
        return True


class FakeReservationRepository:
    def __init__(self) -> None:
        self.reservations: dict[uuid.UUID, CreditReservation] = {}

    async def get(self, reservation_id):
        return self.reservations.get(reservation_id)

    async def get_locked(self, reservation_id):
        return self.reservations.get(reservation_id)

    async def list_stale_pending(self, org_id, now):
        return [
            r
            for r in self.reservations.values()
            if r.organization_id == org_id
            and r.status == ReservationStatus.PENDING
            and r.expires_at <= now
        ]

    async def list_orgs_with_stale_pending(self, now, limit=500):
        return []

    async def list_pending(self, org_id):
        return [
            r
            for r in self.reservations.values()
            if r.organization_id == org_id and r.status == ReservationStatus.PENDING
        ]

    async def add(self, reservation):
        self.reservations[reservation.id] = reservation


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.entries: list = []

    def add(self, tx):
        self.entries.append(tx)

    async def exists_with_idempotency_key(self, key):
        return any(tx.idempotency_key == key for tx in self.entries)

    async def list_for_org(self, org_id, limit, offset):
        return [tx for tx in self.entries if tx.organization_id == org_id]

    async def count_for_org(self, org_id):
        return sum(1 for tx in self.entries if tx.organization_id == org_id)

    def of_type(self, type):
        return [tx for tx in self.entries if tx.type == type]


# -- LLM-specific fakes -------------------------------------------------------


class FakeLlmGateway:
    """Canned LLM gateway: returns a fixed result, or raises on complete()."""

    def __init__(
        self,
        *,
        result: LlmResult | None = None,
        complete_error: Exception | None = None,
        configured_error: Exception | None = None,
        model: str = "fake-model-1",
    ) -> None:
        self.result = result
        self.complete_error = complete_error
        self.configured_error = configured_error
        self.model = model
        self.complete_calls = 0

    def check_configured(self, provider: LlmProvider) -> None:
        if self.configured_error is not None:
            raise self.configured_error

    def model_for(self, provider: LlmProvider) -> str:
        return self.model

    async def complete(self, provider, prompt, max_tokens) -> LlmResult:
        self.complete_calls += 1
        if self.complete_error is not None:
            raise self.complete_error
        assert self.result is not None
        return self.result


class FakeLlmCallRepository:
    def __init__(self) -> None:
        self.calls: list[LlmCall] = []

    async def add(self, call: LlmCall) -> None:
        self.calls.append(call)

    async def get(self, call_id: uuid.UUID) -> LlmCall | None:
        return next((c for c in self.calls if c.id == call_id), None)


def build_engine(org_id: uuid.UUID, balance: int) -> tuple[CreditEngine, FakeLedgerRepository]:
    wallets = FakeWalletRepository()
    wallets.wallets[org_id] = CreditWallet(
        organization_id=org_id, balance=balance, allowance_period=_period()
    )
    reservations = FakeReservationRepository()
    ledger = FakeLedgerRepository()
    engine = CreditEngine(wallets, reservations, ledger)
    engine._wallets_repo = wallets  # expose for assertions
    return engine, ledger


# -- tests --------------------------------------------------------------------


async def test_start_then_finalize_success_captures_credits_and_bounds_preview():
    org_id = uuid.uuid4()
    engine, ledger = build_engine(org_id, balance=10)
    long_text = "x" * (RESPONSE_PREVIEW_CHARS + 500)
    gateway = FakeLlmGateway(result=LlmResult(text=long_text, tokens_in=3, tokens_out=7))
    calls = FakeLlmCallRepository()

    call = await StartLlmCall(calls, engine, gateway).execute(
        org_id, None, LlmProvider.OPENAI, "hello", max_tokens=128
    )

    # Accepted: pending call persisted, hold placed, balance already reduced.
    assert call.status == LlmCallStatus.PENDING
    assert engine._wallets_repo.wallets[org_id].balance == 9

    # Worker settles: provider result stored, hold captured.
    result = await gateway.complete(LlmProvider.OPENAI, "hello", 128)
    await FinalizeLlmCall(calls, engine).execute(call.id, result=result)

    assert call.status == LlmCallStatus.SUCCEEDED
    assert call.response_text == long_text  # full text stored untouched
    assert call.response_preview is not None
    assert len(call.response_preview) == RESPONSE_PREVIEW_CHARS  # bounded

    reservation = next(iter(engine.reservations.reservations.values()))
    assert reservation.status == ReservationStatus.CAPTURED
    assert engine._wallets_repo.wallets[org_id].balance == 9


async def test_finalize_with_error_releases_hold_and_persists_failure():
    org_id = uuid.uuid4()
    engine, ledger = build_engine(org_id, balance=10)
    gateway = FakeLlmGateway(complete_error=RuntimeError("provider 500"))
    calls = FakeLlmCallRepository()

    call = await StartLlmCall(calls, engine, gateway).execute(
        org_id, None, LlmProvider.GEMINI, "hello", max_tokens=64
    )
    assert engine._wallets_repo.wallets[org_id].balance == 9  # hold placed

    # Worker hits a provider error and finalizes with it.
    await FinalizeLlmCall(calls, engine).execute(call.id, error="provider 500")

    # The hold was released -> balance restored.
    assert engine._wallets_repo.wallets[org_id].balance == 10
    reservation = next(iter(engine.reservations.reservations.values()))
    assert reservation.status == ReservationStatus.RELEASED
    assert ledger.of_type(TransactionType.RELEASE)

    # A FAILED audit row persisted with the error.
    assert len(calls.calls) == 1
    assert calls.calls[0].status == LlmCallStatus.FAILED
    assert "provider 500" in (calls.calls[0].error or "")


async def test_start_not_configured_creates_no_reservation():
    org_id = uuid.uuid4()
    engine, ledger = build_engine(org_id, balance=10)
    gateway = FakeLlmGateway(configured_error=LlmProviderNotConfigured("no key for anthropic"))
    calls = FakeLlmCallRepository()

    try:
        await StartLlmCall(calls, engine, gateway).execute(
            org_id, None, LlmProvider.ANTHROPIC, "hi", max_tokens=32
        )
        raise AssertionError("expected LlmProviderNotConfigured")
    except LlmProviderNotConfigured:
        pass

    # Fail-fast before holding credits: no reservation, no HOLD ledger entry.
    assert engine.reservations.reservations == {}
    assert ledger.of_type(TransactionType.HOLD) == []
    assert gateway.complete_calls == 0
    assert calls.calls == []


async def test_finalize_is_idempotent_on_settled_calls():
    org_id = uuid.uuid4()
    engine, _ledger = build_engine(org_id, balance=10)
    gateway = FakeLlmGateway(result=LlmResult(text="ok", tokens_in=1, tokens_out=1))
    calls = FakeLlmCallRepository()

    call = await StartLlmCall(calls, engine, gateway).execute(
        org_id, None, LlmProvider.OPENAI, "hello", max_tokens=32
    )
    finalize = FinalizeLlmCall(calls, engine)
    await finalize.execute(call.id, result=LlmResult(text="ok", tokens_in=1, tokens_out=1))
    # acks_late redelivery: a second finalize must not double-settle.
    await finalize.execute(call.id, error="late duplicate")

    assert call.status == LlmCallStatus.SUCCEEDED
    assert engine._wallets_repo.wallets[org_id].balance == 9
