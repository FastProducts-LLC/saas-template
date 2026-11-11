"""Feature-flag use cases."""

import uuid

from app.domains.feature_flags.application.ports import FeatureFlagRepository
from app.domains.feature_flags.domain.entities import KNOWN_FLAGS, FeatureFlag
from app.domains.feature_flags.domain.errors import UnknownFeatureFlag


class GetPublicConfig:
    """Effective flag map for clients: KNOWN_FLAGS defaults, DB rows winning."""

    def __init__(self, repo: FeatureFlagRepository) -> None:
        self.repo = repo

    async def execute(self) -> dict[str, bool]:
        flags = dict(KNOWN_FLAGS)
        for row in await self.repo.list_all():
            if row.key in flags:
                flags[row.key] = row.enabled
        return flags


class ListFeatureFlags:
    """Admin view — every known flag with its audit fields (None when the
    flag has never been toggled and only the default applies)."""

    def __init__(self, repo: FeatureFlagRepository) -> None:
        self.repo = repo

    async def execute(self) -> list[tuple[str, bool, FeatureFlag | None]]:
        rows = {row.key: row for row in await self.repo.list_all()}
        return [
            (key, rows[key].enabled if key in rows else default, rows.get(key))
            for key, default in KNOWN_FLAGS.items()
        ]


class SetFeatureFlag:
    def __init__(self, repo: FeatureFlagRepository) -> None:
        self.repo = repo

    async def execute(self, key: str, *, enabled: bool, by: uuid.UUID | None) -> FeatureFlag:
        if key not in KNOWN_FLAGS:
            raise UnknownFeatureFlag(f"Unknown feature flag: {key}.")
        flag = await self.repo.get(key)
        if flag is None:
            flag = FeatureFlag(key=key, enabled=enabled, updated_by=by)
            await self.repo.add(flag)
        else:
            flag.set_enabled(enabled, by=by)
        return flag
