"""Admin domain — public surface."""

from app.domains.admin.domain.entities import AdminAuditEntry
from app.domains.admin.domain.errors import (
    AdminErrorRecordNotFound,
    AdminInvitationNotFound,
    AdminOrgNotFound,
    AdminUserNotFound,
    CannotDeactivateSelf,
    CannotImpersonateInactive,
    CannotImpersonateSuperuser,
    MergeInvalid,
    NotSuperuser,
)

__all__ = [
    "AdminAuditEntry",
    "AdminErrorRecordNotFound",
    "AdminInvitationNotFound",
    "AdminOrgNotFound",
    "AdminUserNotFound",
    "CannotDeactivateSelf",
    "CannotImpersonateInactive",
    "CannotImpersonateSuperuser",
    "MergeInvalid",
    "NotSuperuser",
]
