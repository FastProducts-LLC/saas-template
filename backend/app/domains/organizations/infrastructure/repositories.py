"""Organizations repository: tenant-scoped data access.

Every query here is scoped by organization_id — this layer is what keeps
tenants isolated. New features should follow the same pattern.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.auth.infrastructure.orm  # noqa: F401  (User mapping for joins)
import app.domains.organizations.infrastructure.orm  # noqa: F401
from app.domains.auth.domain import User
from app.domains.organizations.domain import (
    AlreadyMember,
    Invitation,
    Membership,
    Organization,
    Role,
)

UNIQUE_VIOLATION = "23505"  # PostgreSQL SQLSTATE


class SqlAlchemyOrgRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- organizations -------------------------------------------------------

    async def get(self, org_id: uuid.UUID) -> Organization | None:
        return await self.db.get(Organization, org_id)

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_email_domain(self, domain: str) -> Organization | None:
        stmt = select(Organization).where(Organization.email_domain == domain.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Organization, Membership]]:
        stmt = (
            select(Organization, Membership)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user_id)
            .order_by(Organization.created_at)
        )
        return [(org, m) for org, m in (await self.db.execute(stmt)).all()]

    async def add(self, org: Organization) -> None:
        self.db.add(org)
        await self.db.flush()

    async def delete(self, org: Organization) -> None:
        await self.db.delete(org)

    # -- memberships ---------------------------------------------------------

    async def get_membership(self, org_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
        stmt = select(Membership).where(
            Membership.organization_id == org_id, Membership.user_id == user_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_membership_by_id(
        self, org_id: uuid.UUID, membership_id: uuid.UUID
    ) -> Membership | None:
        stmt = select(Membership).where(
            Membership.organization_id == org_id, Membership.id == membership_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_membership_by_email(self, org_id: uuid.UUID, email: str) -> Membership | None:
        stmt = (
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.organization_id == org_id,
                func.lower(User.email) == email.lower(),
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_members(self, org_id: uuid.UUID) -> list[tuple[Membership, User]]:
        stmt = (
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == org_id)
            .order_by(Membership.created_at)
        )
        return [(m, u) for m, u in (await self.db.execute(stmt)).all()]

    async def count_seats(self, org_id: uuid.UUID) -> int:
        # One statement observes acceptance (invitation -> membership) atomically.
        members = (
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == org_id,
            )
            .scalar_subquery()
        )
        pending = (
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.organization_id == org_id,
                Invitation.accepted_at.is_(None),
                Invitation.expires_at > datetime.now(UTC),
            )
            .scalar_subquery()
        )
        return (await self.db.execute(select(members + pending))).scalar_one()

    async def count_owners(self, org_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == org_id, Membership.role == Role.OWNER)
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def add_membership(self, membership: Membership) -> None:
        self.db.add(membership)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            # Race backstop: use cases pre-check membership, but concurrent
            # requests (e.g. parallel accepts of one invitation) all pass the
            # check — the (organization_id, user_id) unique constraint decides.
            # Losers get the same clean 409 as the sequential case, not a 500.
            if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
                raise AlreadyMember("You are already a member of this organization.") from exc
            raise

    async def delete_membership(self, membership: Membership) -> None:
        await self.db.delete(membership)

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    # -- invitations ---------------------------------------------------------

    async def add_invitation(self, invitation: Invitation) -> None:
        self.db.add(invitation)
        await self.db.flush()

    async def list_pending_invitations(self, org_id: uuid.UUID) -> list[Invitation]:
        stmt = (
            select(Invitation)
            .where(Invitation.organization_id == org_id, Invitation.accepted_at.is_(None))
            .order_by(Invitation.created_at)
        )
        return list((await self.db.execute(stmt)).scalars())

    async def get_invitation(
        self, org_id: uuid.UUID, invitation_id: uuid.UUID
    ) -> Invitation | None:
        stmt = select(Invitation).where(
            Invitation.organization_id == org_id, Invitation.id == invitation_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_invitation_by_hash(self, token_hash: str) -> Invitation | None:
        stmt = select(Invitation).where(Invitation.token_hash == token_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_pending_invitation_by_email(
        self, org_id: uuid.UUID, email: str
    ) -> Invitation | None:
        stmt = select(Invitation).where(
            Invitation.organization_id == org_id,
            func.lower(Invitation.email) == email.lower(),
            Invitation.accepted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def delete_invitation(self, invitation: Invitation) -> None:
        await self.db.delete(invitation)
