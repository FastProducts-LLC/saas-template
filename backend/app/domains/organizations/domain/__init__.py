"""Organizations domain — public surface for other slices."""

from app.domains.organizations.domain.actor import Actor, ActorType
from app.domains.organizations.domain.entities import Invitation, Membership, Organization, Role
from app.domains.organizations.domain.errors import (
    AlreadyMember,
    DomainAlreadyClaimed,
    DomainNotClaimable,
    DomainOrgExists,
    InsufficientRole,
    InvitationInvalid,
    LastOwnerError,
    MemberNotFound,
    OrganizationNotFound,
    OrgSuspended,
)
from app.domains.organizations.domain.services import (
    PUBLIC_EMAIL_DOMAINS,
    email_domain_of,
    ensure_removal_allowed,
    ensure_role_change_allowed,
    normalize_claimable_domain,
    resolve_auto_claim_domain,
    slugify,
)

__all__ = [
    "PUBLIC_EMAIL_DOMAINS",
    "Actor",
    "ActorType",
    "AlreadyMember",
    "DomainAlreadyClaimed",
    "DomainNotClaimable",
    "DomainOrgExists",
    "InsufficientRole",
    "Invitation",
    "InvitationInvalid",
    "LastOwnerError",
    "MemberNotFound",
    "Membership",
    "Organization",
    "OrganizationNotFound",
    "OrgSuspended",
    "Role",
    "email_domain_of",
    "ensure_removal_allowed",
    "ensure_role_change_allowed",
    "normalize_claimable_domain",
    "resolve_auto_claim_domain",
    "slugify",
]
