"""Generation cancel / finalize / delete unit tests.

Use cases are constructed directly over in-memory fakes — a generation repo, a
media store recording deletes, and a credits stub recording capture/release.
No database, no HTTP client, no conftest fixtures used.
"""

import uuid

from app.domains.credits.domain import CreditAction
from app.domains.generations.application.use_cases import (
    CancelGeneration,
    DeleteGeneration,
    FinalizeGeneration,
)
from app.domains.generations.domain import (
    Generation,
    GenerationStatus,
    NotCancelable,
    NotDeletable,
)

# -- fakes --------------------------------------------------------------------


class FakeGenerationRepository:
    def __init__(self) -> None:
        self.generations: dict[uuid.UUID, Generation] = {}

    async def get(self, generation_id):
        return self.generations.get(generation_id)

    async def get_for_org(self, org_id, generation_id):
        gen = self.generations.get(generation_id)
        if gen is None or gen.organization_id != org_id:
            return None
        return gen

    async def list_for_org(self, org_id, limit, offset):
        return [g for g in self.generations.values() if g.organization_id == org_id]

    async def add(self, generation):
        self.generations[generation.id] = generation

    async def remove(self, generation):
        self.generations.pop(generation.id, None)


class FakeMediaStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def save(self, org_id, name, asset):
        return f"{org_id}/{name}"

    def extension_for(self, mime_type):
        return ".bin"

    async def delete(self, file_path):
        self.deleted.append(file_path)


class FakeCredits:
    """Records capture/release calls; satisfies the CreditService port."""

    def __init__(self) -> None:
        self.captured: list[uuid.UUID] = []
        self.released: list[tuple[uuid.UUID, str | None]] = []

    async def reserve(self, org_id, user_id, action, reference=None):
        raise AssertionError("reserve should not be called by these use cases")

    async def capture(self, reservation_id):
        self.captured.append(reservation_id)

    async def release(self, reservation_id, reason=None):
        self.released.append((reservation_id, reason))


def make_generation(
    *,
    org_id: uuid.UUID,
    status: GenerationStatus = GenerationStatus.PENDING,
    reservation_id: uuid.UUID | None = None,
    file_path: str | None = None,
) -> Generation:
    return Generation(
        organization_id=org_id,
        kind=CreditAction.IMAGE_GPT,
        model="fake-model",
        prompt="a cat",
        status=status,
        reservation_id=reservation_id,
        file_path=file_path,
    )


# -- tests --------------------------------------------------------------------


async def test_cancel_pending_releases_credits():
    org_id = uuid.uuid4()
    reservation_id = uuid.uuid4()
    repo = FakeGenerationRepository()
    credits = FakeCredits()
    gen = make_generation(org_id=org_id, reservation_id=reservation_id)
    await repo.add(gen)

    result = await CancelGeneration(repo, credits).execute(org_id, gen.id)

    assert result.status == GenerationStatus.CANCELED
    assert result.completed_at is not None
    assert credits.released == [(reservation_id, "Generation canceled — credits returned")]
    assert credits.captured == []


async def test_cancel_succeeded_raises_and_does_not_release():
    org_id = uuid.uuid4()
    repo = FakeGenerationRepository()
    credits = FakeCredits()
    gen = make_generation(
        org_id=org_id, status=GenerationStatus.SUCCEEDED, reservation_id=uuid.uuid4()
    )
    await repo.add(gen)

    try:
        await CancelGeneration(repo, credits).execute(org_id, gen.id)
        raise AssertionError("expected NotCancelable")
    except NotCancelable:
        pass

    assert credits.released == []
    assert credits.captured == []


async def test_finalize_on_canceled_generation_is_noop():
    org_id = uuid.uuid4()
    repo = FakeGenerationRepository()
    credits = FakeCredits()
    gen = make_generation(
        org_id=org_id, status=GenerationStatus.CANCELED, reservation_id=uuid.uuid4()
    )
    await repo.add(gen)

    await FinalizeGeneration(repo, credits).execute(
        gen.id, file_path="org/x.png", mime_type="image/png"
    )

    # Lost the race with cancel: status untouched, no capture/release.
    assert gen.status == GenerationStatus.CANCELED
    assert credits.captured == []
    assert credits.released == []


async def test_delete_settled_with_file_removes_media_and_row():
    org_id = uuid.uuid4()
    repo = FakeGenerationRepository()
    media = FakeMediaStore()
    gen = make_generation(
        org_id=org_id,
        status=GenerationStatus.SUCCEEDED,
        file_path="org/result.png",
    )
    await repo.add(gen)

    await DeleteGeneration(repo, media).execute(org_id, gen.id)

    assert media.deleted == ["org/result.png"]
    assert gen.id not in repo.generations


async def test_delete_pending_raises_and_touches_nothing():
    org_id = uuid.uuid4()
    repo = FakeGenerationRepository()
    media = FakeMediaStore()
    gen = make_generation(org_id=org_id, status=GenerationStatus.PENDING)
    await repo.add(gen)

    try:
        await DeleteGeneration(repo, media).execute(org_id, gen.id)
        raise AssertionError("expected NotDeletable")
    except NotDeletable:
        pass

    assert media.deleted == []
    assert gen.id in repo.generations
