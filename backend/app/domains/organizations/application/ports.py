"""Organizations application ports."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.domains.auth.domain import User
from app.domains.entitlements.domain import EntitlementKey
from app.domains.organizations.domain import Invitation, Membership, Organization


class OrgRepository(Protocol):
    async def count_seats(self, org_id: uuid.UUID) -> int: ...

    # -- organizations -----------------------------------------------------
    async def get(self, org_id: uuid.UUID) -> Organization | None: ...

    async def get_by_slug(self, slug: str) -> Organization | None: ...

    async def get_by_email_domain(self, domain: str) -> Organization | None: ...

    async def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Organization, Membership]]: ...

    async def add(self, org: Organization) -> None: ...

    async def delete(self, org: Organization) -> None: ...

    # -- memberships --------------------------------------------------------
    async def get_membership(self, org_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None: ...

    async def get_membership_by_id(
        self, org_id: uuid.UUID, membership_id: uuid.UUID
    ) -> Membership | None: ...

    async def get_membership_by_email(self, org_id: uuid.UUID, email: str) -> Membership | None: ...

    async def list_members(self, org_id: uuid.UUID) -> list[tuple[Membership, User]]: ...

    async def count_owners(self, org_id: uuid.UUID) -> int: ...

    async def add_membership(self, membership: Membership) -> None: ...

    async def delete_membership(self, membership: Membership) -> None: ...

    async def get_user(self, user_id: uuid.UUID) -> User | None: ...

    # -- invitations ----------------------------------------------------------
    async def add_invitation(self, invitation: Invitation) -> None: ...

    async def list_pending_invitations(self, org_id: uuid.UUID) -> list[Invitation]: ...

    async def get_invitation(
        self, org_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> Invitation | None: ...

    async def get_invitation_by_hash(self, token_hash: str) -> Invitation | None: ...

    async def get_pending_invitation_by_email(
        self, org_id: uuid.UUID, email: str
    ) -> Invitation | None: ...

    async def delete_invitation(self, invitation: Invitation) -> None: ...


class InviteTokenService(Protocol):
    def new_opaque_token(self) -> tuple[str, str]:
        """Return (raw_token, hash). Only the hash is ever stored."""
        ...

    def hash_token(self, raw: str) -> str: ...


class InvitationNotifier(Protocol):
    """Delivers the invitation email; owns URL construction and copy."""

    async def send_invitation(
        self, invitation: Invitation, org: Organization, inviter: User, raw_token: str
    ) -> None: ...


class EntitlementChecker(Protocol):
    async def ensure_within_limit(
        self, org_id: uuid.UUID, key: EntitlementKey, count: Callable[[], Awaitable[int]]
    ) -> None: ...
