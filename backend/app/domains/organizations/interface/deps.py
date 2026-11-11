"""Organizations composition root + tenant-scoping dependencies.

`require_role(Role.X)` resolves the `{org_id}` path parameter against the
current caller. Auth is either:

- JWT Bearer (session token) — membership + role checked as usual
- API key Bearer (`sk_live_…`) — org-scoped programmatic access at MEMBER
  level only (admin/owner actions still require a JWT session)

It 404s when the caller has no access (so org existence is never leaked),
403s when the org has been suspended by a platform admin, and 403s when
the role is insufficient.

Other feature slices import `CurrentMember` / `CurrentAdmin` / `CurrentOwner`
to scope their endpoints to a tenant. Endpoints that charge credits or write
audit rows use `CurrentActor` instead — it distinguishes session users from
API keys so usage is attributed truthfully (see `organizations.domain.actor`).
"""

import hashlib
import uuid
from functools import cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.policy import API_KEY_PREFIX
from app.core.security import decode_access_token
from app.domains.api_keys.infrastructure.repositories import SqlAlchemyApiKeyRepository
from app.domains.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.domains.auth.infrastructure.security import JwtTokenService
from app.domains.organizations.application import use_cases as uc
from app.domains.organizations.application.queries import OrgQueries
from app.domains.organizations.domain import (
    Actor,
    ActorType,
    InsufficientRole,
    Membership,
    OrganizationNotFound,
    OrgSuspended,
    Role,
)
from app.domains.organizations.infrastructure.notifier import EmailInvitationNotifier
from app.domains.organizations.infrastructure.repositories import SqlAlchemyOrgRepository

DB = Annotated[AsyncSession, Depends(get_db)]

_tokens = JwtTokenService()
_notifier = EmailInvitationNotifier()
_bearer = HTTPBearer(auto_error=False)


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def _actor_from_api_key(
    *,
    org_id: uuid.UUID,
    raw_key: str,
    min_role: Role,
    db: AsyncSession,
) -> Actor:
    """Resolve a sk_live_ key into a MEMBER-level actor for this org.

    API keys are intentionally capped at MEMBER — create/revoke keys, billing,
    and other admin actions still require a JWT session.
    """
    if min_role != Role.MEMBER:
        raise InsufficientRole(
            "API keys can only access member-level endpoints. Sign in to manage the organization."
        )

    key_repo = SqlAlchemyApiKeyRepository(db)
    key = await key_repo.get_by_hash(_hash_api_key(raw_key))
    if key is None or not key.is_active:
        raise AuthenticationError("Invalid or revoked API key.")
    if key.organization_id != org_id:
        # Same 404 shape as missing membership — never leak cross-tenant ids.
        raise OrganizationNotFound("Organization not found.")

    org_repo = SqlAlchemyOrgRepository(db)
    org = await org_repo.get(org_id)
    if org is None:
        raise OrganizationNotFound("Organization not found.")
    if org.is_suspended:
        raise OrgSuspended("This organization has been suspended.")

    key.touch()
    await db.flush()

    return Actor(
        membership=Membership(
            organization_id=key.organization_id,
            user_id=key.created_by_id,
            role=Role.MEMBER,
        ),
        type=ActorType.API_KEY,
        api_key_id=key.id,
    )


async def _actor_from_jwt(
    *,
    org_id: uuid.UUID,
    token: str,
    min_role: Role,
    db: AsyncSession,
) -> Actor:
    user_id = decode_access_token(token)
    if user_id is None:
        raise AuthenticationError("Invalid or expired access token.")
    user = await SqlAlchemyUserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")

    repo = SqlAlchemyOrgRepository(db)
    membership = await repo.get_membership(org_id, user.id)
    if membership is None:
        raise OrganizationNotFound("Organization not found.")
    # Checked after membership so org existence still never leaks.
    org = await repo.get(org_id)
    if org is not None and org.is_suspended:
        raise OrgSuspended("This organization has been suspended.")
    if not membership.role.at_least(min_role):
        raise InsufficientRole("Your role does not permit this action.")
    return Actor(membership=membership, type=ActorType.USER)


@cache
def require_actor(min_role: Role = Role.MEMBER):
    """Resolve the caller into an `Actor` (session user or API key).

    Memoized so `require_actor(X)` always returns the same callable: FastAPI's
    per-request dependency cache is keyed on callable identity, so a route
    using both `CurrentActor` and `CurrentMember` resolves auth exactly once
    (one DB lookup, one `key.touch()`).
    """

    async def dependency(
        org_id: uuid.UUID,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
        db: DB,
    ) -> Actor:
        if credentials is None:
            raise AuthenticationError("Missing bearer token.")
        token = credentials.credentials
        if token.startswith(API_KEY_PREFIX):
            return await _actor_from_api_key(org_id=org_id, raw_key=token, min_role=min_role, db=db)
        return await _actor_from_jwt(org_id=org_id, token=token, min_role=min_role, db=db)

    return dependency


@cache
def require_role(min_role: Role = Role.MEMBER):
    actor_dep = require_actor(min_role)

    async def dependency(actor: Annotated[Actor, Depends(actor_dep)]) -> Membership:
        return actor.membership

    return dependency


CurrentActor = Annotated[Actor, Depends(require_actor(Role.MEMBER))]
CurrentMember = Annotated[Membership, Depends(require_role(Role.MEMBER))]
CurrentAdmin = Annotated[Membership, Depends(require_role(Role.ADMIN))]
CurrentOwner = Annotated[Membership, Depends(require_role(Role.OWNER))]


def get_org_queries(db: DB) -> OrgQueries:
    return OrgQueries(SqlAlchemyOrgRepository(db))


# For other slices' routers (billing, admin) — keeps their imports on this
# composition root instead of reaching into organizations' application layer.
OrgQueriesDep = Annotated[OrgQueries, Depends(get_org_queries)]


def get_create_org(db: DB) -> uc.CreateOrganization:
    return uc.CreateOrganization(
        SqlAlchemyOrgRepository(db), domain_claim_mode=settings.domain_claim_mode
    )


def get_rename_org(db: DB) -> uc.RenameOrganization:
    return uc.RenameOrganization(SqlAlchemyOrgRepository(db))


def get_delete_org(db: DB) -> uc.DeleteOrganization:
    return uc.DeleteOrganization(SqlAlchemyOrgRepository(db))


def get_set_org_domain(db: DB) -> uc.SetOrgDomain:
    return uc.SetOrgDomain(
        SqlAlchemyOrgRepository(db), domain_claim_mode=settings.domain_claim_mode
    )


def build_auto_join(db: AsyncSession) -> uc.AutoJoinByEmailDomain:
    """For other slices' composition roots (auth wires this into VerifyEmail)."""
    from app.domains.entitlements.interface.deps import build_entitlement_service

    return uc.AutoJoinByEmailDomain(
        SqlAlchemyOrgRepository(db), entitlements=build_entitlement_service(db)
    )


def get_change_member_role(db: DB) -> uc.ChangeMemberRole:
    return uc.ChangeMemberRole(SqlAlchemyOrgRepository(db))


def get_remove_member(db: DB) -> uc.RemoveMember:
    return uc.RemoveMember(SqlAlchemyOrgRepository(db))


def get_invite_member(db: DB) -> uc.InviteMember:
    from app.domains.entitlements.interface.deps import build_entitlement_service

    return uc.InviteMember(
        SqlAlchemyOrgRepository(db),
        _tokens,
        _notifier,
        settings.invitation_ttl_days,
        entitlements=build_entitlement_service(db),
    )


def get_revoke_invitation(db: DB) -> uc.RevokeInvitation:
    return uc.RevokeInvitation(SqlAlchemyOrgRepository(db))


def get_accept_invitation(db: DB) -> uc.AcceptInvitation:
    return uc.AcceptInvitation(SqlAlchemyOrgRepository(db), _tokens)


def build_seat_counter(db: AsyncSession) -> SqlAlchemyOrgRepository:
    """Export tenant-scoped occupied and reserved seat counts to other slices."""
    return SqlAlchemyOrgRepository(db)
