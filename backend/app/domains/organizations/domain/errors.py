"""Organizations domain errors."""

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError


class OrganizationNotFound(NotFoundError):
    code = "organization_not_found"
    internal_code = "ERR_PERM_002"


class MemberNotFound(NotFoundError):
    code = "member_not_found"
    internal_code = "ERR_ORG_003"


class InsufficientRole(PermissionDeniedError):
    code = "insufficient_role"
    internal_code = "ERR_PERM_001"


class LastOwnerError(ConflictError):
    code = "last_owner"
    internal_code = "ERR_ORG_001"


class AlreadyMember(ConflictError):
    code = "already_member"
    internal_code = "ERR_ORG_002"


class InvitationInvalid(NotFoundError):
    code = "invitation_invalid"
    internal_code = "ERR_PERM_003"


class OrgSuspended(PermissionDeniedError):
    code = "org_suspended"
    internal_code = "ERR_ORG_004"


class DomainNotClaimable(AppError):
    code = "domain_not_claimable"
    internal_code = "ERR_ORG_005"


class DomainAlreadyClaimed(ConflictError):
    code = "domain_already_claimed"
    internal_code = "ERR_ORG_006"


class DomainOrgExists(ConflictError):
    code = "domain_org_exists"
    internal_code = "ERR_ORG_007"
