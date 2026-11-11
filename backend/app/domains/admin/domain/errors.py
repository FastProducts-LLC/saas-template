"""Admin domain: platform-level (cross-tenant) admin errors.

Superuser status lives on the User entity (`users.is_superuser`) and is
granted by flipping that flag manually in the database. Everything here
operates across tenants, so it must only ever be reachable behind the
superuser check in the admin interface.
"""

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError


class NotSuperuser(PermissionDeniedError):
    code = "not_superuser"
    internal_code = "ERR_PERM_004"


class AdminUserNotFound(NotFoundError):
    code = "user_not_found"
    internal_code = "ERR_ADM_001"


class AdminOrgNotFound(NotFoundError):
    code = "organization_not_found"
    internal_code = "ERR_ADM_002"


class CannotDeactivateSelf(ConflictError):
    code = "cannot_deactivate_self"
    internal_code = "ERR_ADM_003"


class AdminErrorRecordNotFound(NotFoundError):
    code = "error_record_not_found"
    internal_code = "ERR_ADM_004"


class CannotImpersonateSuperuser(ConflictError):
    code = "cannot_impersonate_superuser"
    internal_code = "ERR_ADM_005"


class CannotImpersonateInactive(ConflictError):
    code = "cannot_impersonate_inactive"
    internal_code = "ERR_ADM_006"


class AdminInvitationNotFound(NotFoundError):
    code = "invitation_not_found"
    internal_code = "ERR_ADM_007"


class MergeInvalid(ConflictError):
    code = "merge_invalid"
    internal_code = "ERR_ADM_008"
