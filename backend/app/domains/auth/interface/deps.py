"""Auth composition root + the `CurrentUser` dependency other slices import.

This is the ONLY place auth use cases meet their concrete adapters. Swapping
an adapter (e.g. a different hasher or mailer) is a one-line change here.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_claims, decode_access_token
from app.domains.audit.interface.deps import get_audit_recorder
from app.domains.auth.application import use_cases as uc
from app.domains.auth.application.ports import AuditRecorder
from app.domains.auth.domain import EmailNotVerified, ImpersonationNotAllowed, User
from app.domains.auth.infrastructure.lockout import RedisLoginAttemptTracker
from app.domains.auth.infrastructure.mailer import ProviderMarketingList, TransactionalAuthMailer
from app.domains.auth.infrastructure.repositories import (
    SqlAlchemyMarketingPreferencesRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from app.domains.auth.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.domains.auth.infrastructure.session_revoker import AutonomousSessionRevoker

DB = Annotated[AsyncSession, Depends(get_db)]
# Overridable in tests (bind the recorder to the test DB); satisfies the
# slice-local AuditRecorder port structurally.
Audit = Annotated[AuditRecorder, Depends(get_audit_recorder)]

_hasher = Argon2PasswordHasher()
_tokens = JwtTokenService()
_mailer = TransactionalAuthMailer()
_marketing = ProviderMarketingList()
_login_attempts = RedisLoginAttemptTracker(
    window_seconds=settings.login_lockout_window_minutes * 60,
    lockout_seconds=settings.login_lockout_duration_minutes * 60,
)


def get_register_user(db: DB) -> uc.RegisterUser:
    return uc.RegisterUser(
        SqlAlchemyUserRepository(db),
        _hasher,
        _mailer,
        _marketing,
        enumeration_safe=settings.signup_enumeration_protection,
    )


def get_login_user(db: DB, audit: Audit) -> uc.LoginUser:
    return uc.LoginUser(
        SqlAlchemyUserRepository(db),
        SqlAlchemyRefreshTokenRepository(db),
        _hasher,
        _tokens,
        settings.refresh_token_ttl_days,
        _login_attempts,
        audit,
        settings.login_lockout_max_attempts,
        account_max_failed_attempts=settings.login_lockout_account_max_attempts,
        require_verified_at_login=settings.email_verification_gate == "login",
        hide_unverified=settings.signup_enumeration_protection,
    )


def get_session_revoker() -> AutonomousSessionRevoker:
    """A dependency (not a module singleton) so tests can bind it to the test
    database — it opens its own sessions, like the audit recorder."""
    return AutonomousSessionRevoker(SessionLocal)


def get_refresh_session(
    db: DB,
    audit: Audit,
    session_revoker: Annotated[AutonomousSessionRevoker, Depends(get_session_revoker)],
) -> uc.RefreshSession:
    return uc.RefreshSession(
        SqlAlchemyRefreshTokenRepository(db),
        _tokens,
        settings.refresh_token_ttl_days,
        session_revoker,
        audit,
    )


def get_logout_user(db: DB) -> uc.LogoutUser:
    return uc.LogoutUser(SqlAlchemyRefreshTokenRepository(db), _tokens)


def get_verify_email(db: DB) -> uc.VerifyEmail:
    # Imported here, not at module level: organizations' deps imports
    # CurrentUser from this module, so a top-level import would be circular.
    from app.domains.organizations.interface.deps import build_auto_join

    return uc.VerifyEmail(SqlAlchemyUserRepository(db), _tokens, build_auto_join(db))


def get_resend_verification() -> uc.ResendVerification:
    return uc.ResendVerification(_mailer)


def get_forgot_password(db: DB) -> uc.ForgotPassword:
    return uc.ForgotPassword(SqlAlchemyUserRepository(db), _tokens, _mailer)


def get_reset_password(db: DB, audit: Audit) -> uc.ResetPassword:
    return uc.ResetPassword(
        SqlAlchemyUserRepository(db),
        SqlAlchemyRefreshTokenRepository(db),
        _hasher,
        _tokens,
        audit,
        _mailer,
        _login_attempts,
    )


def get_update_profile() -> uc.UpdateProfile:
    return uc.UpdateProfile(_marketing)


def get_change_password(db: DB, audit: Audit) -> uc.ChangePassword:
    return uc.ChangePassword(
        SqlAlchemyRefreshTokenRepository(db),
        _hasher,
        _tokens,
        settings.refresh_token_ttl_days,
        audit,
        _mailer,
    )


def build_marketing_preferences_repository(
    db: AsyncSession,
) -> SqlAlchemyMarketingPreferencesRepository:
    """Marketing/suppression writer on the auth-owned `users` table, for other
    slices' composition roots (satisfies their ports structurally)."""
    return SqlAlchemyMarketingPreferencesRepository(db)


_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DB,
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AuthenticationError("Invalid or expired access token.")
    user = await SqlAlchemyUserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user


async def get_current_verified_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Like CurrentUser, but honors EMAIL_VERIFICATION_GATE (sensitive|login).

    Use on mutating / billing / AI / org-create routes. Leave /auth/me,
    verify, and resend on CurrentUser so unverified users can finish setup.
    When the gate is ``none``, this is a no-op.
    """
    if settings.email_verification_gate == "none":
        return user
    if not user.email_verified:
        raise EmailNotVerified("Confirm your email address before continuing.")
    return user


async def forbid_impersonation(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Route guard: refuse admin impersonation sessions (`imp` claim).

    Put it on routes that create or change a credential outliving the
    15-minute impersonation token — otherwise "view as user" quietly becomes
    "keep permanent access as user". Authentication itself is still done by
    CurrentUser; API-key callers (no JWT) pass through untouched.
    """
    if credentials is None:
        return
    claims = decode_access_claims(credentials.credentials)
    if claims and claims.get("imp"):
        raise ImpersonationNotAllowed("Not available during an impersonation session.")


NoImpersonation = Depends(forbid_impersonation)

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]
