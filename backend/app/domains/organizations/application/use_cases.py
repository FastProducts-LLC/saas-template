"""Organizations use cases: org lifecycle, members, invitations.

Invariants (last-owner, role rules, invitation validity) live in the domain
layer; these classes orchestrate them through ports.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.domains.auth.domain import User
from app.domains.entitlements.domain import EntitlementKey, EntitlementLimitReached
from app.domains.organizations.application.ports import (
    EntitlementChecker,
    InvitationNotifier,
    InviteTokenService,
    OrgRepository,
)
from app.domains.organizations.domain import (
    AlreadyMember,
    DomainAlreadyClaimed,
    DomainOrgExists,
    InsufficientRole,
    Invitation,
    InvitationInvalid,
    MemberNotFound,
    Membership,
    Organization,
    Role,
    email_domain_of,
    ensure_removal_allowed,
    ensure_role_change_allowed,
    normalize_claimable_domain,
    resolve_auto_claim_domain,
    slugify,
)


class CreateOrganization:
    def __init__(self, orgs: OrgRepository, domain_claim_mode: str = "verified_claim") -> None:
        self.orgs = orgs
        self.domain_claim_mode = domain_claim_mode

    async def execute(
        self, user: User, name: str, intended_use: str = ""
    ) -> tuple[Organization, Membership]:
        auto_domain = resolve_auto_claim_domain(
            email=user.email,
            email_verified=user.email_verified,
            mode=self.domain_claim_mode,  # type: ignore[arg-type]
        )
        if auto_domain is not None:
            existing = await self.orgs.get_by_email_domain(auto_domain)
            if existing:
                raise DomainOrgExists(
                    "Your company already has a workspace. "
                    "Verify your email to join automatically, or ask "
                    "the workspace owner for an invitation."
                )
        org = Organization(
            name=name,
            slug=await self._unique_slug(name),
            intended_use=intended_use,
            email_domain=auto_domain,
        )
        await self.orgs.add(org)
        membership = Membership(organization_id=org.id, user_id=user.id, role=Role.OWNER)
        await self.orgs.add_membership(membership)
        return org, membership

    async def _unique_slug(self, name: str) -> str:
        slug = slugify(name)
        if not await self.orgs.get_by_slug(slug):
            return slug
        return f"{slug}-{secrets.token_hex(3)}"


class RenameOrganization:
    def __init__(self, orgs: OrgRepository) -> None:
        self.orgs = orgs

    async def execute(self, org: Organization, name: str) -> Organization:
        org.rename(name)
        return org


class DeleteOrganization:
    """Hard-delete the org (members, keys, billing cascade away)."""

    def __init__(self, orgs: OrgRepository) -> None:
        self.orgs = orgs

    async def execute(self, org: Organization) -> None:
        await self.orgs.delete(org)


class SetOrgDomain:
    """Claim (or release, with domain=None) the org's company email domain.

    Claiming requires the acting owner to hold a *verified* address on that
    domain; once claimed, users who verify a matching email auto-join as
    members (see AutoJoinByEmailDomain).
    """

    def __init__(self, orgs: OrgRepository, domain_claim_mode: str = "verified_claim") -> None:
        self.orgs = orgs
        self.domain_claim_mode = domain_claim_mode

    async def execute(self, org: Organization, owner: User, domain: str | None) -> Organization:
        if domain is None:
            org.email_domain = None
            return org
        normalized = normalize_claimable_domain(
            domain,
            owner.email,
            email_verified=owner.email_verified,
            mode=self.domain_claim_mode,  # type: ignore[arg-type]
        )
        holder = await self.orgs.get_by_email_domain(normalized)
        if holder and holder.id != org.id:
            raise DomainAlreadyClaimed("Another organization has already claimed that domain.")
        org.email_domain = normalized
        return org


class AutoJoinByEmailDomain:
    """Add a user to the org that claimed their email domain, if any.

    Called after email verification — never before, so typing someone else's
    company domain into the signup form grants nothing. A no-op for unclaimed
    domains, suspended orgs, and existing members, which makes it safe to call
    on every verification (links can be clicked twice).
    """

    def __init__(self, orgs: OrgRepository, entitlements: EntitlementChecker | None = None) -> None:
        self.orgs = orgs
        self.entitlements = entitlements

    async def execute(self, user: User) -> Membership | None:
        org = await self.orgs.get_by_email_domain(email_domain_of(user.email))
        if org is None or org.is_suspended:
            return None
        if await self.orgs.get_membership(org.id, user.id):
            return None
        if self.entitlements is not None:
            try:
                await self.entitlements.ensure_within_limit(
                    org.id, EntitlementKey.SEATS, lambda: self.orgs.count_seats(org.id)
                )
            except EntitlementLimitReached:
                return None
        membership = Membership(organization_id=org.id, user_id=user.id, role=Role.MEMBER)
        await self.orgs.add_membership(membership)
        return membership


class ChangeMemberRole:
    def __init__(self, orgs: OrgRepository) -> None:
        self.orgs = orgs

    async def execute(
        self, actor: Membership, membership_id: uuid.UUID, new_role: Role
    ) -> Membership:
        target = await self.orgs.get_membership_by_id(actor.organization_id, membership_id)
        if not target:
            raise MemberNotFound("Member not found.")
        owner_count = await self.orgs.count_owners(actor.organization_id)
        ensure_role_change_allowed(actor, target, new_role, owner_count)
        target.role = new_role
        return target


class RemoveMember:
    def __init__(self, orgs: OrgRepository) -> None:
        self.orgs = orgs

    async def execute(self, actor: Membership, membership_id: uuid.UUID) -> None:
        target = await self.orgs.get_membership_by_id(actor.organization_id, membership_id)
        if not target:
            raise MemberNotFound("Member not found.")
        owner_count = await self.orgs.count_owners(actor.organization_id)
        ensure_removal_allowed(actor, target, owner_count)
        await self.orgs.delete_membership(target)


class InviteMember:
    def __init__(
        self,
        orgs: OrgRepository,
        tokens: InviteTokenService,
        notifier: InvitationNotifier,
        invitation_ttl_days: int,
        entitlements: EntitlementChecker | None = None,
    ) -> None:
        self.orgs = orgs
        self.tokens = tokens
        self.notifier = notifier
        self.invitation_ttl_days = invitation_ttl_days
        self.entitlements = entitlements

    async def execute(self, org: Organization, inviter: User, email: str, role: Role) -> Invitation:
        if role == Role.OWNER:
            raise InsufficientRole("Owners cannot be invited; promote a member instead.")
        if await self.orgs.get_membership_by_email(org.id, email):
            raise AlreadyMember("That email already belongs to a member.")
        if await self.orgs.get_pending_invitation_by_email(org.id, email):
            raise AlreadyMember("An invitation for that email is already pending.")

        if self.entitlements is not None:
            await self.entitlements.ensure_within_limit(
                org.id, EntitlementKey.SEATS, lambda: self.orgs.count_seats(org.id)
            )
        raw, token_hash = self.tokens.new_opaque_token()
        invitation = Invitation(
            organization_id=org.id,
            email=email.lower(),
            role=role,
            token_hash=token_hash,
            invited_by_id=inviter.id,
            expires_at=datetime.now(UTC) + timedelta(days=self.invitation_ttl_days),
        )
        await self.orgs.add_invitation(invitation)
        await self.notifier.send_invitation(invitation, org, inviter, raw)
        return invitation


class RevokeInvitation:
    def __init__(self, orgs: OrgRepository) -> None:
        self.orgs = orgs

    async def execute(self, org_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        invitation = await self.orgs.get_invitation(org_id, invitation_id)
        if not invitation or not invitation.is_pending:
            raise InvitationInvalid("Invitation not found.")
        await self.orgs.delete_invitation(invitation)


class AcceptInvitation:
    def __init__(self, orgs: OrgRepository, tokens: InviteTokenService) -> None:
        self.orgs = orgs
        self.tokens = tokens

    async def execute(self, user: User, raw_token: str) -> tuple[Organization, Membership]:
        invitation = await self.orgs.get_invitation_by_hash(self.tokens.hash_token(raw_token))
        if not invitation:
            raise InvitationInvalid("This invitation is invalid or has expired.")
        invitation.assert_acceptable_by(user.email)
        if await self.orgs.get_membership(invitation.organization_id, user.id):
            raise AlreadyMember("You are already a member of this organization.")

        membership = invitation.accept(user.id)
        await self.orgs.add_membership(membership)
        org = await self.orgs.get(invitation.organization_id)
        assert org is not None  # noqa: S101 — invitation FK guarantees the org exists
        return org, membership
