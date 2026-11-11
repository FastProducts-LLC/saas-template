"""Actor: who is making a tenant-scoped request — a session user or an API key.

Wraps the resolved (or, for API keys, synthesized) `Membership` so role and
tenancy checks are unchanged, while giving charge/audit code a truthful
attribution pair: `user_id` for session users, `api_key_id` for keys. API-key
usage is never attributed to the key's creator.
"""

import enum
import uuid
from dataclasses import dataclass

from app.domains.organizations.domain.entities import Membership, Role


class ActorType(str, enum.Enum):
    USER = "user"
    API_KEY = "api_key"


@dataclass(frozen=True)
class Actor:
    membership: Membership
    type: ActorType
    api_key_id: uuid.UUID | None = None  # set iff type is API_KEY

    @property
    def organization_id(self) -> uuid.UUID:
        return self.membership.organization_id

    @property
    def role(self) -> Role:
        return self.membership.role

    @property
    def is_api_key(self) -> bool:
        return self.type is ActorType.API_KEY

    @property
    def user_id(self) -> uuid.UUID | None:
        """Attribution user id: the session user, or None for API keys
        (key usage is attributed to `api_key_id`, never the key's creator)."""
        return None if self.is_api_key else self.membership.user_id
