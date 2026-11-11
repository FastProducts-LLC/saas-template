"""Unit + API tests for runtime feature flags and the public config endpoint."""

import uuid

import pytest

from app.domains.feature_flags.application.use_cases import (
    GetPublicConfig,
    ListFeatureFlags,
    SetFeatureFlag,
)
from app.domains.feature_flags.domain import (
    KNOWN_FLAGS,
    FeatureFlag,
    UnknownFeatureFlag,
)
from tests.helpers import make_superuser, register_and_login


class FakeFlagRepo:
    def __init__(self) -> None:
        self.items: list[FeatureFlag] = []

    async def get(self, key: str) -> FeatureFlag | None:
        return next((f for f in self.items if f.key == key), None)

    async def list_all(self) -> list[FeatureFlag]:
        return list(self.items)

    async def add(self, flag: FeatureFlag) -> None:
        self.items.append(flag)


# ---------------------------------------------------------------- use cases


async def test_config_defaults_with_empty_repo():
    flags = await GetPublicConfig(FakeFlagRepo()).execute()
    assert flags == KNOWN_FLAGS


async def test_db_row_wins_over_default():
    repo = FakeFlagRepo()
    await SetFeatureFlag(repo).execute("community", enabled=True, by=uuid.uuid4())
    flags = await GetPublicConfig(repo).execute()
    assert flags["community"] is True


async def test_unknown_row_ignored_in_config():
    repo = FakeFlagRepo()
    # A row for a retired flag key must not leak into the config payload.
    repo.items.append(FeatureFlag(key="retired_module", enabled=True))
    flags = await GetPublicConfig(repo).execute()
    assert "retired_module" not in flags


async def test_set_unknown_key_rejected():
    with pytest.raises(UnknownFeatureFlag):
        await SetFeatureFlag(FakeFlagRepo()).execute("nope", enabled=True, by=None)


async def test_set_upserts_and_records_updater():
    repo = FakeFlagRepo()
    admin = uuid.uuid4()
    flag = await SetFeatureFlag(repo).execute("community", enabled=True, by=admin)
    assert flag.updated_by == admin
    again = await SetFeatureFlag(repo).execute("community", enabled=False, by=admin)
    assert again.id == flag.id  # updated in place, not duplicated
    assert len(repo.items) == 1
    listed = await ListFeatureFlags(repo).execute()
    assert ("community", False) in [(k, e) for k, e, _ in listed]


# ---------------------------------------------------------------- API


async def _superuser(client, db, email="flags-admin@example.com"):
    user, headers = await register_and_login(client, email)
    await make_superuser(db, user["id"])
    return headers


async def test_public_config_needs_no_auth(client):
    res = await client.get("/api/config")
    assert res.status_code == 200
    assert res.json()["features"]["community"] is False


async def test_admin_flags_require_superuser(client):
    _, headers = await register_and_login(client, "member@example.com")
    assert (await client.get("/api/admin/flags", headers=headers)).status_code == 403
    res = await client.put("/api/admin/flags/community", json={"enabled": True}, headers=headers)
    assert res.status_code == 403


async def test_toggle_round_trip(client, db):
    headers = await _superuser(client, db)

    res = await client.put("/api/admin/flags/community", json={"enabled": True}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["enabled"] is True

    assert (await client.get("/api/config")).json()["features"]["community"] is True

    listed = (await client.get("/api/admin/flags", headers=headers)).json()["items"]
    row = next(f for f in listed if f["key"] == "community")
    assert row["enabled"] is True and row["updated_by"] is not None

    res = await client.put("/api/admin/flags/community", json={"enabled": False}, headers=headers)
    assert res.status_code == 200
    assert (await client.get("/api/config")).json()["features"]["community"] is False


async def test_unknown_flag_404(client, db):
    headers = await _superuser(client, db)
    res = await client.put("/api/admin/flags/nope", json={"enabled": True}, headers=headers)
    assert res.status_code == 404
    assert res.json()["code"] == "ERR_FLAG_001"
