"""Auth domain errors. Every `internal_code` exists in shared/errors.toml."""

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    PermissionDeniedError,
    RateLimited,
)


class InvalidCredentials(AuthenticationError):
    code = "invalid_credentials"
    internal_code = "ERR_AUTH_001"


class AccountTemporarilyLocked(RateLimited):
    """Login lockout tripped — carries Retry-After via RateLimited.retry_after."""

    code = "account_locked"
    internal_code = "ERR_AUTH_006"


class SessionExpired(AuthenticationError):
    """Refresh-token path failure — the frontend signs the user out on this."""

    code = "session_expired"
    internal_code = "ERR_AUTH_002"


class InvalidActionToken(AppError):
    """Email-link token (verification / password reset) failed validation."""

    code = "invalid_action_token"
    internal_code = "ERR_AUTH_004"


class EmailAlreadyRegistered(ConflictError):
    code = "email_already_registered"
    internal_code = "ERR_VAL_002"


class PasswordTooWeak(AppError):
    code = "password_too_weak"
    internal_code = "ERR_VAL_003"


class PasswordMismatch(AppError):
    code = "password_mismatch"
    internal_code = "ERR_VAL_004"


class TermsNotAccepted(AppError):
    code = "terms_not_accepted"
    internal_code = "ERR_VAL_005"


class EmailNotVerified(PermissionDeniedError):
    """Session user has not confirmed their mailbox; gated by EMAIL_VERIFICATION_GATE."""

    code = "email_not_verified"
    internal_code = "ERR_AUTH_005"


class ImpersonationNotAllowed(PermissionDeniedError):
    """A credential-level action attempted from an admin impersonation session."""

    code = "impersonation_not_allowed"
    internal_code = "ERR_AUTH_007"
