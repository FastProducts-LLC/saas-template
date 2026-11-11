"""Cookie/tracking consent audit trail.

Append-only: every banner decision by a signed-in user becomes a new event —
never an overwrite — so consent is provable per GDPR Art. 7(1). The current
state is simply the latest event. Anonymous visitors keep a client-side
record only (see frontend/src/features/consent).

The `categories` dict holds non-essential category grants (today just
"analytics"); strictly-necessary flows are implicit and never recorded as
consented because they don't require consent.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class ConsentEvent:
    user_id: uuid.UUID
    categories: dict[str, bool]
    policy_version: str
    ip_address: str | None = None
    user_agent: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def analytics(self) -> bool:
        return bool(self.categories.get("analytics", False))
