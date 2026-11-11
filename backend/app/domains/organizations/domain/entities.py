"""Organizations domain entities — the multi-tenancy core, pure Python.

Every tenant-scoped table in the system carries an `organization_id`;
access is always resolved through a Membership.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domains.organizations.domain.errors import InvitationInvalid


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

    @property
    def rank(self) -> int:
        return {Role.MEMBER: 0, Role.ADMIN: 1, Role.OWNER: 2}[self]

    def at_least(self, other: "Role") -> bool:
        return self.rank >= other.rank


@dataclass(eq=False)
class Organization:
    name: str
    slug: str
    # Platform-admin suspension: null = active. Members of a suspended org are
    # locked out of every /orgs/{org_id}/* route (enforced in require_role).
    suspended_at: datetime | None = None
    # Claimed company email domain (e.g. "intel.com"). Users who verify an
    # email on this domain auto-join as members. One org per domain.
    email_domain: str | None = None
    intended_use: str = ""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def rename(self, name: str) -> None:
        self.name = name

    @property
    def is_suspended(self) -> bool:
        return self.suspended_at is not None

    def suspend(self) -> None:
        self.suspended_at = self.suspended_at or _utcnow()

    def unsuspend(self) -> None:
        self.suspended_at = None


@dataclass(eq=False)
class Membership:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: Role = Role.MEMBER
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(eq=False)
class Invitation:
    organization_id: uuid.UUID
    email: str
    role: Role
    token_hash: str
    expires_at: datetime
    invited_by_id: uuid.UUID | None = None
    accepted_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None

    def assert_acceptable_by(self, email: str) -> None:
        """Raise InvitationInvalid unless this invitation can be accepted by
        the given address right now."""
        if not self.is_pending or self.expires_at < _utcnow():
            raise InvitationInvalid("This invitation is invalid or has expired.")
        if self.email != email.lower():
            raise InvitationInvalid("This invitation was sent to a different email address.")

    def accept(self, user_id: uuid.UUID) -> Membership:
        """Consume the invitation, producing the resulting membership."""
        self.accepted_at = _utcnow()
        return Membership(organization_id=self.organization_id, user_id=user_id, role=self.role)
