"""Auth domain — the only module other slices may import from this slice
(besides `interface.deps`). Re-exports the public domain surface."""

from app.domains.auth.domain.entities import RefreshToken, User
from app.domains.auth.domain.errors import (
    AccountTemporarilyLocked,
    EmailAlreadyRegistered,
    EmailNotVerified,
    ImpersonationNotAllowed,
    InvalidActionToken,
    InvalidCredentials,
    PasswordMismatch,
    PasswordTooWeak,
    SessionExpired,
    TermsNotAccepted,
)
from app.domains.auth.domain.services import (
    COMMON_PASSWORDS,
    PASSWORD_MIN_LENGTH,
    validate_password_strength,
)

__all__ = [
    "COMMON_PASSWORDS",
    "PASSWORD_MIN_LENGTH",
    "AccountTemporarilyLocked",
    "EmailAlreadyRegistered",
    "EmailNotVerified",
    "ImpersonationNotAllowed",
    "InvalidActionToken",
    "InvalidCredentials",
    "PasswordMismatch",
    "PasswordTooWeak",
    "RefreshToken",
    "SessionExpired",
    "TermsNotAccepted",
    "User",
    "validate_password_strength",
]
