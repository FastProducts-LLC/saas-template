"""Organizations domain services — pure policy functions.

The membership rules need an owner count, which only persistence knows;
callers (use cases) fetch it and pass it in, keeping these functions pure
and unit-testable without a database.
"""

import re
from typing import Literal

from app.core.email_validation import PUBLIC_EMAIL_DOMAINS, email_domain_of
from app.domains.organizations.domain.entities import Membership, Role
from app.domains.organizations.domain.errors import (
    DomainNotClaimable,
    InsufficientRole,
    LastOwnerError,
)

_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")

DomainClaimMode = Literal["off", "verified_claim", "manual_only"]


def resolve_auto_claim_domain(
    *,
    email: str,
    email_verified: bool,
    mode: DomainClaimMode,
) -> str | None:
    """Domain to attach on org create, or None if claiming is deferred/disabled.

    ``verified_claim`` (template default) only returns a domain after mailbox
    proof — prevents squatting a company domain with an unverified address.
    """
    if mode in ("off", "manual_only"):
        return None
    if not email_verified:
        return None
    domain = email_domain_of(email)
    if domain in PUBLIC_EMAIL_DOMAINS:
        return None
    return domain


def normalize_claimable_domain(
    domain: str,
    claimant_email: str,
    *,
    email_verified: bool = True,
    mode: DomainClaimMode = "verified_claim",
) -> str:
    """Validate and normalize a company domain claim.

    The claimant must hold a *verified* address on the domain — that is the
    only proof of affiliation required at this stage (no DNS verification yet).
    """
    if mode == "off":
        raise DomainNotClaimable("Company domain claiming is disabled for this product.")
    if not email_verified:
        raise DomainNotClaimable("Verify your email before claiming a company domain.")
    normalized = domain.strip().lower().removeprefix("http://").removeprefix("https://")
    normalized = normalized.removeprefix("www.").rstrip("/")
    if normalized.startswith("@"):
        normalized = normalized[1:]
    if not _DOMAIN_RE.match(normalized):
        raise DomainNotClaimable("That doesn't look like a valid domain name.")
    if normalized in PUBLIC_EMAIL_DOMAINS:
        raise DomainNotClaimable(
            "Shared email providers can't be claimed — use your company's own domain."
        )
    if email_domain_of(claimant_email) != normalized:
        raise DomainNotClaimable("You can only claim the domain of your own email address.")
    return normalized


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:50] or "org"


def ensure_role_change_allowed(
    actor: Membership, target: Membership, new_role: Role, owner_count: int
) -> None:
    # Only owners may grant or revoke the owner role.
    if Role.OWNER in (new_role, target.role) and actor.role != Role.OWNER:
        raise InsufficientRole("Only an owner can change owner roles.")
    if target.role == Role.OWNER and new_role != Role.OWNER and owner_count <= 1:
        raise LastOwnerError("An organization must keep at least one owner.")


def ensure_removal_allowed(actor: Membership, target: Membership, owner_count: int) -> None:
    # Admins+ can remove others; anyone can remove themselves (leave).
    if target.user_id != actor.user_id and not actor.role.at_least(Role.ADMIN):
        raise InsufficientRole("Only admins can remove other members.")
    if target.role == Role.OWNER and owner_count <= 1:
        raise LastOwnerError("An organization must keep at least one owner.")
