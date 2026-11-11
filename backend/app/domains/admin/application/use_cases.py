"""Admin use cases: platform stats, moderation, and support actions.

Read endpoints (lists) go straight from the interface layer to the
AdminRepository port — CQRS-lite, there are no invariants on reads.

Every mutation records an AdminAuditEntry through the same repository, in
the same transaction, *after* its guards pass — rejected operations leave
no audit row.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domains.admin.application.ports import (
    AdminRepository,
    Analytics,
    CreditAdjuster,
    SessionRevoker,
)
from app.domains.admin.domain import (
    AdminAuditEntry,
    AdminInvitationNotFound,
    AdminOrgNotFound,
    AdminUserNotFound,
    CannotDeactivateSelf,
    CannotImpersonateInactive,
    CannotImpersonateSuperuser,
    MergeInvalid,
)
from app.domains.auth.domain import User
from app.domains.credits.domain import CreditWallet
from app.domains.organizations.domain import Organization


class ImpersonationTokenService(Protocol):
    def create_impersonation_token(self, target_user_id: str, impersonator_id: str) -> str: ...


async def _audit(
    repo: AdminRepository,
    actor: User,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    **meta,
) -> None:
    await repo.add_audit_entry(
        AdminAuditEntry(
            actor_user_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
        )
    )


@dataclass(frozen=True)
class PlatformStats:
    total_users: int
    active_users: int
    total_organizations: int


class GetPlatformStats:
    def __init__(self, repo: AdminRepository) -> None:
        self.repo = repo

    async def execute(self) -> PlatformStats:
        return PlatformStats(
            total_users=await self.repo.count_users(),
            active_users=await self.repo.count_users(active_only=True),
            total_organizations=await self.repo.count_organizations(),
        )


class GetAnalytics:
    def __init__(self, repo: AdminRepository) -> None:
        self.repo = repo

    async def execute(self) -> Analytics:
        return await self.repo.get_analytics()


class SetUserActive:
    def __init__(self, repo: AdminRepository, refresh_tokens: SessionRevoker) -> None:
        self.repo = repo
        self.refresh_tokens = refresh_tokens

    async def execute(self, acting_user: User, user_id: uuid.UUID, *, active: bool) -> User:
        if not active and user_id == acting_user.id:
            raise CannotDeactivateSelf("You cannot deactivate your own account.")
        user = await self.repo.get_user(user_id)
        if user is None:
            raise AdminUserNotFound("User not found.")
        user.is_active = active
        if not active:
            # Kill every session now — otherwise the refresh cookie would
            # keep working until each token expired.
            await self.refresh_tokens.revoke_all_for_user(user.id)
        await _audit(
            self.repo,
            acting_user,
            "user.deactivate" if not active else "user.reactivate",
            "user",
            user.id,
            email=user.email,
        )
        return user


class SignOutUserEverywhere:
    def __init__(self, repo: AdminRepository, refresh_tokens: SessionRevoker) -> None:
        self.repo = repo
        self.refresh_tokens = refresh_tokens

    async def execute(self, acting_user: User, user_id: uuid.UUID) -> User:
        user = await self.repo.get_user(user_id)
        if user is None:
            raise AdminUserNotFound("User not found.")
        await self.refresh_tokens.revoke_all_for_user(user.id)
        await _audit(
            self.repo, acting_user, "user.signout_everywhere", "user", user.id, email=user.email
        )
        return user


class ImpersonateUser:
    def __init__(self, repo: AdminRepository, tokens: ImpersonationTokenService) -> None:
        self.repo = repo
        self.tokens = tokens

    async def execute(self, acting_user: User, user_id: uuid.UUID) -> tuple[str, User]:
        user = await self.repo.get_user(user_id)
        if user is None:
            raise AdminUserNotFound("User not found.")
        # Also blocks self-impersonation: the acting user is a superuser.
        if user.is_superuser:
            raise CannotImpersonateSuperuser("Superusers cannot be impersonated.")
        if not user.is_active:
            raise CannotImpersonateInactive("Deactivated users cannot be impersonated.")
        token = self.tokens.create_impersonation_token(str(user.id), str(acting_user.id))
        await _audit(self.repo, acting_user, "user.impersonate", "user", user.id, email=user.email)
        return token, user


class SetOrgSuspended:
    def __init__(self, repo: AdminRepository) -> None:
        self.repo = repo

    async def execute(
        self, acting_user: User, org_id: uuid.UUID, *, suspended: bool
    ) -> Organization:
        org = await self.repo.get_organization(org_id)
        if org is None:
            raise AdminOrgNotFound("Organization not found.")
        if suspended:
            org.suspend()
        else:
            org.unsuspend()
        await _audit(
            self.repo,
            acting_user,
            "org.suspend" if suspended else "org.unsuspend",
            "organization",
            org.id,
            name=org.name,
        )
        return org


class AdjustOrgCredits:
    def __init__(self, repo: AdminRepository, engine: CreditAdjuster) -> None:
        self.repo = repo
        self.engine = engine

    async def execute(
        self, acting_user: User, org_id: uuid.UUID, *, amount: int, description: str
    ) -> CreditWallet:
        org = await self.repo.get_organization(org_id)
        if org is None:
            raise AdminOrgNotFound("Organization not found.")
        wallet = await self.engine.adjust(org_id, amount, description, user_id=acting_user.id)
        await _audit(
            self.repo,
            acting_user,
            "credits.adjust",
            "organization",
            org.id,
            amount=amount,
            description=description,
            balance_after=wallet.balance,
        )
        # The flush above expires the wallet's server-generated updated_at;
        # re-load it so the interface layer can serialize without sync IO.
        await self.repo.refresh(wallet)
        return wallet


class RevokeInvitationAdmin:
    def __init__(self, repo: AdminRepository) -> None:
        self.repo = repo

    async def execute(self, acting_user: User, invitation_id: uuid.UUID) -> None:
        invitation = await self.repo.get_invitation(invitation_id)
        if invitation is None or not invitation.is_pending:
            raise AdminInvitationNotFound("Invitation not found.")
        await self.repo.delete_invitation(invitation)
        await _audit(
            self.repo,
            acting_user,
            "invitation.revoke",
            "invitation",
            invitation.id,
            email=invitation.email,
            organization_id=str(invitation.organization_id),
        )


class MergeOrganizations:
    """Merge one or more source organizations into a target.

    Moves all members (skipping duplicates) and org-scoped data, then
    deletes the source orgs. Audit-logged per source.
    """

    def __init__(self, repo: AdminRepository) -> None:
        self.repo = repo

    async def execute(
        self,
        acting_user: User,
        target_id: uuid.UUID,
        source_ids: list[uuid.UUID],
    ) -> int:
        if target_id in source_ids:
            raise MergeInvalid("Target organization cannot also be a source.")
        target = await self.repo.get_organization(target_id)
        if target is None:
            raise AdminOrgNotFound("Target organization not found.")
        for sid in source_ids:
            src = await self.repo.get_organization(sid)
            if src is None:
                raise AdminOrgNotFound(f"Source organization {sid} not found.")

        moved = await self.repo.merge_organizations(target_id, source_ids)

        for sid in source_ids:
            await _audit(
                self.repo,
                acting_user,
                "org.merge",
                "organization",
                target_id,
                source_id=str(sid),
                members_moved=moved,
            )
        return moved
