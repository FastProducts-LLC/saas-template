"""Generations tests: HTTP create/poll/download, the FinalizeGeneration use
case (credit settlement), and the Celery task entry point.

The worker (`execute_generation`/`_finalize`) builds its own `SessionLocal`
sessions, which target the *dev* database (settings.database_url) — not the
`app_test` database the HTTP app is overridden onto. So the worker can never
see rows created in a test. We therefore:

  * patch the router's `enqueue_generation` to a no-op so creating a
    generation over HTTP never touches Celery or the worker, and
  * exercise the worker-level settlement logic directly through the
    `FinalizeGeneration` use case against the test `db` session.
"""

import uuid

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.domains.credits.domain import (
    ACTIONS,
    CreditAction,
    CreditReservation,
    ReservationStatus,
)
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.generations.application.use_cases import FinalizeGeneration
from app.domains.generations.domain import Generation, GenerationStatus
from app.domains.generations.infrastructure.repositories import (
    SqlAlchemyGenerationRepository,
)
from tests.helpers import create_org, register_and_login

IMAGE_COST = ACTIONS[CreditAction.IMAGE_NANO_BANANA].cost  # 5
VIDEO_COST = ACTIONS[CreditAction.VIDEO_VEO].cost  # 50
SEED_CREDITS = 50  # explicit test seed — there is no free monthly allowance


def _create_payload(kind: CreditAction = CreditAction.IMAGE_NANO_BANANA, prompt="a cat"):
    return {"kind": kind.value, "prompt": prompt}


async def _member(client):
    """Register a user and create an org they own; returns (org_id, headers)."""
    _user, headers = await register_and_login(client)
    org = await create_org(client, headers)
    return org["id"], headers


async def _wallet(client, org_id, headers) -> dict:
    res = await client.get(f"/api/orgs/{org_id}/credits", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


async def _seed_credits(db, org_id, amount: int = SEED_CREDITS) -> None:
    """Grant credits directly — orgs start at zero (no free allowance)."""
    engine = build_credit_engine(db)
    await engine.grant(uuid.UUID(str(org_id)), amount, "Test seed")
    await db.commit()


@pytest.fixture
def _gemini_key(monkeypatch):
    """Make the Gemini-backed kinds (image nano-banana, VEO video) pass
    `check_configured` without a real key. The DispatchingProviderGateway
    reads settings live, so monkeypatching is enough."""
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    yield


@pytest.fixture(autouse=True)
def _no_enqueue(monkeypatch):
    """Never let the create endpoint hand work to Celery/the worker."""
    monkeypatch.setattr(
        "app.domains.generations.interface.router.enqueue_generation",
        lambda *a, **k: None,
    )
    yield


# ── HTTP: create generation ──────────────────────────────────────────


async def test_create_generation_holds_credits_and_returns_pending(client, db, _gemini_key):
    org_id, headers = await _member(client)
    await _seed_credits(db, org_id)
    before = await _wallet(client, org_id, headers)
    assert before["balance"] == SEED_CREDITS

    res = await client.post(
        f"/api/orgs/{org_id}/generations", json=_create_payload(), headers=headers
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == GenerationStatus.PENDING.value
    assert body["kind"] == CreditAction.IMAGE_NANO_BANANA.value
    assert body["credits_cost"] == IMAGE_COST
    assert body["has_file"] is False
    assert body["model"]  # provider model was resolved

    after = await _wallet(client, org_id, headers)
    assert after["balance"] == SEED_CREDITS - IMAGE_COST
    assert after["reserved"] == IMAGE_COST


async def test_create_generation_provider_not_configured_holds_no_credits(client, db):
    # Keys are empty by default — IMAGE_NANO_BANANA needs Gemini.
    org_id, headers = await _member(client)
    await _seed_credits(db, org_id)

    res = await client.post(
        f"/api/orgs/{org_id}/generations", json=_create_payload(), headers=headers
    )
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "ERR_GEN_002"

    # check_configured fails *before* any credits are held.
    after = await _wallet(client, org_id, headers)
    assert after["balance"] == SEED_CREDITS
    assert after["reserved"] == 0


async def test_create_generation_insufficient_credits(client, db, _gemini_key):
    org_id, headers = await _member(client)
    await _seed_credits(db, org_id)

    # VEO costs the entire seed (50); the first succeeds.
    first = await client.post(
        f"/api/orgs/{org_id}/generations",
        json=_create_payload(CreditAction.VIDEO_VEO, "a clip"),
        headers=headers,
    )
    assert first.status_code == 202, first.text
    assert (await _wallet(client, org_id, headers))["balance"] == 0

    # The second has nothing left to hold.
    second = await client.post(
        f"/api/orgs/{org_id}/generations",
        json=_create_payload(CreditAction.VIDEO_VEO, "another clip"),
        headers=headers,
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "ERR_CRD_001"
    assert second.json()["params"] == {"required": 50, "available": 0}


async def test_create_generation_non_member_is_404(client, _gemini_key):
    # Owner creates the org; an unrelated user has no membership.
    org_id, _owner_headers = await _member(client)
    _other, other_headers = await register_and_login(client, email="other@example.com")

    res = await client.post(
        f"/api/orgs/{org_id}/generations",
        json=_create_payload(),
        headers=other_headers,
    )
    assert res.status_code == 404, res.text


async def test_create_generation_rejects_non_generation_kind(client, _gemini_key):
    org_id, headers = await _member(client)
    # LLM_CALL is a valid CreditAction but not a generation kind.
    res = await client.post(
        f"/api/orgs/{org_id}/generations",
        json={"kind": CreditAction.LLM_CALL.value, "prompt": "hi"},
        headers=headers,
    )
    assert res.status_code == 422, res.text  # schema validator rejects it


# ── HTTP: list / get / download ──────────────────────────────────────


async def test_list_generations(client, db, _gemini_key):
    org_id, headers = await _member(client)
    await _seed_credits(db, org_id)
    for prompt in ("one", "two"):
        res = await client.post(
            f"/api/orgs/{org_id}/generations",
            json=_create_payload(prompt=prompt),
            headers=headers,
        )
        assert res.status_code == 202, res.text

    res = await client.get(f"/api/orgs/{org_id}/generations", headers=headers)
    assert res.status_code == 200, res.text
    items = res.json()
    assert len(items) == 2
    assert {i["prompt"] for i in items} == {"one", "two"}


async def test_get_generation(client, db, _gemini_key):
    org_id, headers = await _member(client)
    await _seed_credits(db, org_id)
    created = (
        await client.post(
            f"/api/orgs/{org_id}/generations", json=_create_payload(), headers=headers
        )
    ).json()

    res = await client.get(f"/api/orgs/{org_id}/generations/{created['id']}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["id"] == created["id"]


async def test_get_unknown_generation_is_not_found(client):
    org_id, headers = await _member(client)
    res = await client.get(f"/api/orgs/{org_id}/generations/{uuid.uuid4()}", headers=headers)
    assert res.status_code == 404, res.text
    assert res.json()["code"] == "ERR_GEN_001"


async def test_download_unknown_generation_is_not_found(client):
    org_id, headers = await _member(client)
    res = await client.get(f"/api/orgs/{org_id}/generations/{uuid.uuid4()}/file", headers=headers)
    assert res.status_code == 404, res.text
    assert res.json()["code"] == "ERR_GEN_001"


async def test_download_pending_generation_result_not_ready(client, db, _gemini_key):
    org_id, headers = await _member(client)
    await _seed_credits(db, org_id)
    created = (
        await client.post(
            f"/api/orgs/{org_id}/generations", json=_create_payload(), headers=headers
        )
    ).json()

    res = await client.get(f"/api/orgs/{org_id}/generations/{created['id']}/file", headers=headers)
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "ERR_GEN_004"


# ── Use case: FinalizeGeneration (worker settlement, on the test db) ──


async def _real_org(client) -> uuid.UUID:
    """A committed organization row, so the FKs on credit/generation tables
    (organization_id -> organizations.id) are satisfied when we seed via db."""
    org_id, _headers = await _member(client)
    return uuid.UUID(org_id)


async def _seed_pending(db, org_id: uuid.UUID, kind=CreditAction.IMAGE_NANO_BANANA):
    """Reserve credits + persist a pending Generation, exactly as
    StartGeneration would, but against the test `db` session so the worker
    settlement logic can be exercised without the dev-db worker session."""
    engine = build_credit_engine(db)
    await engine.grant(org_id, SEED_CREDITS, "Test seed")
    reservation = await engine.reserve(org_id, None, kind)
    generation = Generation(
        organization_id=org_id,
        user_id=None,
        kind=kind,
        model="test-model",
        prompt="a cat",
        reservation_id=reservation.id,
        credits_cost=reservation.amount,
    )
    await SqlAlchemyGenerationRepository(db).add(generation)
    await db.commit()
    return generation, reservation


async def _refetch(db, model, pk):
    db.expire_all()
    return await db.get(model, pk)


async def test_finalize_success_captures_reservation(client, db):
    org_id = await _real_org(client)
    generation, reservation = await _seed_pending(db, org_id)
    gen_id, res_id = generation.id, reservation.id  # plain values: _refetch expires all objects

    use_case = FinalizeGeneration(SqlAlchemyGenerationRepository(db), build_credit_engine(db))
    await use_case.execute(gen_id, file_path=f"{org_id}/{gen_id}.png", mime_type="image/png")
    await db.commit()

    g = await _refetch(db, Generation, gen_id)
    assert g.status == GenerationStatus.SUCCEEDED
    assert g.has_file
    assert g.mime_type == "image/png"

    r = await _refetch(db, CreditReservation, res_id)
    assert r.status == ReservationStatus.CAPTURED
    # Capture does not refund: the hold-time deduction sticks.
    assert (await _wallet_balance(db, org_id)) == SEED_CREDITS - IMAGE_COST


async def test_finalize_failure_releases_reservation_and_refunds(client, db):
    org_id = await _real_org(client)
    generation, reservation = await _seed_pending(db, org_id)
    gen_id, res_id = generation.id, reservation.id  # plain values: _refetch expires all objects

    use_case = FinalizeGeneration(SqlAlchemyGenerationRepository(db), build_credit_engine(db))
    await use_case.execute(gen_id, error="provider exploded")
    await db.commit()

    g = await _refetch(db, Generation, gen_id)
    assert g.status == GenerationStatus.FAILED
    assert g.error == "provider exploded"
    assert g.has_file is False

    r = await _refetch(db, CreditReservation, res_id)
    assert r.status == ReservationStatus.RELEASED
    # Release refunds the hold: balance is whole again.
    assert (await _wallet_balance(db, org_id)) == SEED_CREDITS


async def test_finalize_is_idempotent(client, db):
    org_id = await _real_org(client)
    generation, reservation = await _seed_pending(db, org_id)
    gen_id, res_id = generation.id, reservation.id  # plain values: _refetch expires all objects
    use_case = FinalizeGeneration(SqlAlchemyGenerationRepository(db), build_credit_engine(db))

    await use_case.execute(gen_id, file_path=f"{org_id}/{gen_id}.png", mime_type="image/png")
    await db.commit()

    # A redelivery: the generation is no longer pending, and the reservation
    # is already captured — settling it again must not change anything.
    await use_case.execute(gen_id, file_path=f"{org_id}/{gen_id}.png", mime_type="image/png")
    await db.commit()

    g = await _refetch(db, Generation, gen_id)
    assert g.status == GenerationStatus.SUCCEEDED
    r = await _refetch(db, CreditReservation, res_id)
    assert r.status == ReservationStatus.CAPTURED
    assert (await _wallet_balance(db, org_id)) == SEED_CREDITS - IMAGE_COST


async def test_finalize_missing_generation_is_noop(db):
    use_case = FinalizeGeneration(SqlAlchemyGenerationRepository(db), build_credit_engine(db))
    # No exception, no effect.
    await use_case.execute(uuid.uuid4(), file_path="x/y.png", mime_type="image/png")
    await db.commit()


async def test_finalize_persists_artifact_when_cancel_won_the_race():
    """A cancel released the hold first, but the provider still produced a
    result: the artifact must be persisted (file_path/mime_type) without
    re-capturing credits. Use-case level with in-memory port fakes."""

    class _Repo:
        def __init__(self, gen):
            self._gen = gen

        async def get(self, generation_id):
            return self._gen if generation_id == self._gen.id else None

    class _Credits:
        def __init__(self):
            self.captured = []
            self.released = []

        async def capture(self, reservation_id):
            self.captured.append(reservation_id)

        async def release(self, reservation_id, reason=None):
            self.released.append(reservation_id)

    gen = Generation(
        organization_id=uuid.uuid4(),
        user_id=None,
        kind=CreditAction.IMAGE_NANO_BANANA,
        model="test-model",
        prompt="a cat",
        reservation_id=uuid.uuid4(),
        status=GenerationStatus.CANCELED,  # cancel already settled the hold
    )
    credits = _Credits()
    await FinalizeGeneration(_Repo(gen), credits).execute(
        gen.id, file_path="org/result.png", mime_type="image/png"
    )

    # Artifact persisted, but status untouched and no credit settlement.
    assert gen.file_path == "org/result.png"
    assert gen.mime_type == "image/png"
    assert gen.status == GenerationStatus.CANCELED
    assert credits.captured == []
    assert credits.released == []


async def test_finalize_after_cancel_with_error_persists_nothing():
    """A failed provider result after a cancel: no artifact to keep, no
    settlement (the hold was already released by the cancel)."""

    class _Repo:
        def __init__(self, gen):
            self._gen = gen

        async def get(self, generation_id):
            return self._gen if generation_id == self._gen.id else None

    class _Credits:
        def __init__(self):
            self.captured = []
            self.released = []

        async def capture(self, reservation_id):
            self.captured.append(reservation_id)

        async def release(self, reservation_id, reason=None):
            self.released.append(reservation_id)

    gen = Generation(
        organization_id=uuid.uuid4(),
        user_id=None,
        kind=CreditAction.IMAGE_NANO_BANANA,
        model="test-model",
        prompt="a cat",
        reservation_id=uuid.uuid4(),
        status=GenerationStatus.CANCELED,
    )
    credits = _Credits()
    await FinalizeGeneration(_Repo(gen), credits).execute(gen.id, error="boom")

    assert gen.file_path is None
    assert gen.status == GenerationStatus.CANCELED
    assert credits.captured == [] and credits.released == []


async def _wallet_balance(db, org_id: uuid.UUID) -> int:
    from app.domains.credits.domain import CreditWallet

    db.expire_all()
    stmt = select(CreditWallet).where(CreditWallet.organization_id == org_id)
    wallet = (await db.execute(stmt)).scalar_one()
    return wallet.balance


# ── Celery task entry point ──────────────────────────────────────────
#
# run_generation -> run_async -> asyncio.run(...). asyncio.run() raises if a
# loop is already running, so this MUST be a *sync* test (no running pytest-
# asyncio loop), not an `async def`.


def test_run_generation_invokes_worker(monkeypatch):
    from app.domains.generations import tasks

    called: list[uuid.UUID] = []

    async def _fake_execute(generation_id):
        called.append(generation_id)

    # tasks.py imports execute_generation by name at module load, so patch it
    # at the tasks module (the import site).
    monkeypatch.setattr(tasks, "execute_generation", _fake_execute)

    gen_id = uuid.uuid4()
    tasks.run_generation(str(gen_id))  # runs the task body synchronously

    assert called == [gen_id]


async def test_member_api_never_returns_raw_worker_error(client, db):
    """Provider exception text can carry endpoints/request ids: members get
    the catalog code + copy; the raw text stays in the DB for superusers."""
    from app.domains.generations.interface.schemas import GenerationOut

    org_id = await _real_org(client)
    generation, _ = await _seed_pending(db, org_id)
    generation.fail("HTTPError: 401 for https://api.provider.example/v1?key=sk-secret")
    out = GenerationOut.from_entity(generation)
    assert out.error_code == "ERR_GEN_003"
    assert "sk-secret" not in (out.error or "")
    assert "credits for it have been returned" in out.error
    assert generation.error.startswith("HTTPError")  # preserved for admins
