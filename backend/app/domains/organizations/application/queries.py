"""Organizations read operations (CQRS-lite): no invariants, just lookups.

Routers call these instead of touching repositories directly, so the
interface layer stays free of persistence concerns.
"""

import uuid

from app.domains.auth.domain import User
from app.domains.organizations.application.ports import OrgRepository
from app.domains.organizations.domain import (
    Invitation,
    Membership,
    Organization,
    OrganizationNotFound,
)


class OrgQueries:
    def __init__(self, orgs: OrgRepository) -> None:
        self.orgs = orgs

    async def get_org(self, org_id: uuid.UUID) -> Organization:
        org = await self.orgs.get(org_id)
        if org is None:
            raise OrganizationNotFound("Organization not found.")
        return org

    async def list_user_orgs(self, user_id: uuid.UUID) -> list[tuple[Organization, Membership]]:
        return await self.orgs.list_for_user(user_id)

    async def list_members(self, org_id: uuid.UUID) -> list[tuple[Membership, User]]:
        return await self.orgs.list_members(org_id)

    async def get_member(self, membership: Membership) -> tuple[Membership, User]:
        user = await self.orgs.get_user(membership.user_id)
        assert user is not None  # noqa: S101 — FK guarantees existence inside a transaction
        return membership, user

    async def list_pending_invitations(self, org_id: uuid.UUID) -> list[Invitation]:
        return await self.orgs.list_pending_invitations(org_id)
