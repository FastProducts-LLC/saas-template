"""Feature-flag application ports — interfaces consumed by use cases."""

from typing import Protocol

from app.domains.feature_flags.domain.entities import FeatureFlag


class FeatureFlagRepository(Protocol):
    async def get(self, key: str) -> FeatureFlag | None: ...
    async def list_all(self) -> list[FeatureFlag]: ...
    async def add(self, flag: FeatureFlag) -> None: ...
