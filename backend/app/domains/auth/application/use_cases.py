"""Auth use cases. Each class is one application-level operation: it
orchestrates domain objects through ports and owns no I/O of its own.

Construction happens in `..interface.deps` (the composition root); tests
construct them directly with fakes.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.domains.audit.domain import AuditEvent
from app.domains.audit.domain import actions as audit_actions
from app.domains.auth.application.ports import (
    AuditRecorder,
    AuthMailer,
    DomainOrgJoiner,
    LoginAttemptTracker,
    MarketingList,
    PasswordHasher,
    RefreshTokenRepository,
    SessionRevoker,
    TokenService,
    UserRepository,
)
from app.domains.auth.domain import (
    AccountTemporarilyLocked,
    EmailAlreadyRegistered,
    EmailNotVerified,
    InvalidActionToken,
    InvalidCredentials,
    PasswordMismatch,
    RefreshToken,
    SessionExpired,
    TermsNotAccepted,
    User,
    validate_password_strength,
)

# Action-token purposes (the `type` claim in purpose-scoped email-link JWTs).
PURPOSE_VERIFY_EMAIL = "email_verify"
PURPOSE_PASSWORD_RESET = "password_reset"  # noqa: S105 — token purpose label, not a secret


def _password_fingerprint(tokens: TokenService, user: User) -> str:
    """Binds a reset link to the current hash → the link is single-use: it
    dies as soon as the password changes."""
    return tokens.hash_token(user.password_hash)[:16]


async def _issue_refresh_token(
    repo: RefreshTokenRepository, tokens: TokenService, user_id: uuid.UUID, ttl_days: int
) -> str:
    raw, token_hash = tokens.new_opaque_token()
    await repo.add(
        RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        )
    )
    return raw


class RegisterUser:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        mailer: AuthMailer,
        marketing: MarketingList,
        *,
        enumeration_safe: bool = False,
    ) -> None:
        self.users = users
        self.hasher = hasher
        self.mailer = mailer
        self.marketing = marketing
        # Verify-first signup: a taken email is not an error. The caller gets
        # None (and must answer exactly as for a new account); the existing
        # owner gets an email instead.
        self.enumeration_safe = enumeration_safe

    async def execute(
        self,
        *,
        email: str,
        password: str,
        password_confirmation: str,
        first_name: str,
        last_name: str,
        terms_accepted: bool,
        marketing_opt_in: bool,
    ) -> User | None:
        if not terms_accepted:
            raise TermsNotAccepted("You must accept the Terms of Service and Privacy Policy.")
        if password != password_confirmation:
            raise PasswordMismatch("Passwords do not match.")
        validate_password_strength(password)
        existing = await self.users.get_by_email(email)
        if existing:
            if not self.enumeration_safe:
                raise EmailAlreadyRegistered("An account with this email already exists.")
            # Same work as the new-account path (one argon2 hash, one email)
            # so response time doesn't give the answer away. The submitted
            # password and names are discarded — never applied to the account.
            self.hasher.hash(password)
            if existing.email_verified:
                await self.mailer.send_account_exists_notice(existing)
            else:
                await self.mailer.send_verification(existing)
            return None
        user = User.register(
            email=email,
            password_hash=self.hasher.hash(password),
            first_name=first_name,
            last_name=last_name,
            marketing_opt_in=marketing_opt_in,
        )
        await self.users.add(user)
        # GDPR: only sync to the marketing email list when explicitly opted in.
        # Transactional email (welcome/activation below) needs no opt-in.
        if user.marketing_opt_in:
            await self.marketing.subscribe(user.email, user.first_name, user.last_name)
        # Welcome email doubles as the activation email (one CTA: confirm email).
        await self.mailer.send_welcome_with_verification(user)
        return user


def _lockout_keys(email: str, ip: str | None) -> tuple[str, str]:
    """(client_key, account_key) for the login-attempt tracker."""
    account_key = email.strip().lower()
    return f"{account_key}|{ip or 'unknown'}", account_key


class LoginUser:
    """Password login with two lockout scopes:

    * client (email + IP): `max_failed_attempts` misses lock that email for
      that IP only. Someone guessing at an account locks themselves out, not
      the owner signing in from elsewhere.
    * account (email, any IP): `account_max_failed_attempts` misses lock the
      email for everyone, bounding guessing spread across many IPs. It is set
      much higher because it is also the one way an attacker can still lock
      the owner out; ResetPassword lifts it. 0 disables it.
    """

    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        refresh_ttl_days: int,
        attempts: LoginAttemptTracker,
        audit: AuditRecorder,
        max_failed_attempts: int,
        *,
        account_max_failed_attempts: int = 0,
        require_verified_at_login: bool = False,
        hide_unverified: bool = False,
    ) -> None:
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.hasher = hasher
        self.tokens = tokens
        self.refresh_ttl_days = refresh_ttl_days
        self.attempts = attempts
        self.audit = audit
        self.max_failed_attempts = max_failed_attempts
        self.account_max_failed_attempts = account_max_failed_attempts
        self.require_verified_at_login = require_verified_at_login
        # Verify-first signup: an unconfirmed account answers exactly like a
        # wrong password (same error, same lockout counting). Otherwise
        # "register, then sign in" would tell a fresh signup ("not verified")
        # apart from an address that already had an account ("invalid").
        self.hide_unverified = hide_unverified

    async def execute(
        self,
        email: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Return (user, access_token, raw_refresh_token)."""
        # Lockout is checked before any DB or argon2 work, so locked,
        # unknown, and wrong-password emails are indistinguishable from the
        # outside.
        client_key, key = _lockout_keys(email, ip)
        remaining = max(
            await self.attempts.lockout_remaining(client_key),
            await self.attempts.lockout_remaining(key),
        )
        if remaining:
            raise AccountTemporarilyLocked(
                "Too many failed sign-in attempts.", retry_after=remaining
            )
        user = await self.users.get_by_email(email)
        if (
            not user
            or not self.hasher.verify(password, user.password_hash)
            or not user.is_active
            or (self.hide_unverified and not user.email_verified)
        ):
            client_failures = await self.attempts.record_failure(client_key)
            account_failures = await self.attempts.record_failure(key)
            scope = None
            if client_failures >= self.max_failed_attempts:
                await self.attempts.lock(client_key)
                scope = "client"
            if 0 < self.account_max_failed_attempts <= account_failures:
                await self.attempts.lock(key)
                scope = "account"
            if scope:
                await self.audit.record(
                    AuditEvent(
                        action=audit_actions.LOCKOUT_TRIGGERED,
                        actor_user_id=user.id if user else None,
                        ip=ip,
                        user_agent=user_agent,
                        # scope=account: this email is now locked for every
                        # client, the owner included.
                        meta={"email": key, "scope": scope},
                    )
                )
            await self.audit.record(
                AuditEvent(
                    action=audit_actions.LOGIN_FAILED,
                    actor_user_id=user.id if user else None,
                    ip=ip,
                    user_agent=user_agent,
                    meta={"email": key},
                )
            )
            raise InvalidCredentials("Invalid email or password.")
        if self.require_verified_at_login and not user.email_verified:
            raise EmailNotVerified("Confirm your email address before signing in.")
        await self.attempts.clear(client_key)
        await self.attempts.clear(key)
        access = self.tokens.create_access_token(str(user.id))
        refresh = await _issue_refresh_token(
            self.refresh_tokens, self.tokens, user.id, self.refresh_ttl_days
        )
        await self.audit.record(
            AuditEvent(
                action=audit_actions.LOGIN_SUCCEEDED,
                actor_user_id=user.id,
                ip=ip,
                user_agent=user_agent,
            )
        )
        return user, access, refresh


class RefreshSession:
    # A rotated token replayed within this window is the benign race (two
    # tabs, or a client retry, presenting the same token) — rejected without
    # treating it as theft. Anything later is reuse.
    REUSE_GRACE = timedelta(seconds=10)

    def __init__(
        self,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        refresh_ttl_days: int,
        session_revoker: SessionRevoker,
        audit: AuditRecorder,
    ) -> None:
        self.refresh_tokens = refresh_tokens
        self.tokens = tokens
        self.refresh_ttl_days = refresh_ttl_days
        self.session_revoker = session_revoker
        self.audit = audit

    async def execute(
        self, raw_token: str, *, ip: str | None = None, user_agent: str | None = None
    ) -> tuple[str, str]:
        """Rotate a refresh token. Return (access_token, new_raw_refresh_token)."""
        token_hash = self.tokens.hash_token(raw_token)
        token = await self.refresh_tokens.get_valid(token_hash)
        if not token:
            await self._handle_possible_reuse(token_hash, ip=ip, user_agent=user_agent)
            raise SessionExpired("Invalid or expired refresh token.")
        token.rotate()
        access = self.tokens.create_access_token(str(token.user_id))
        refresh = await _issue_refresh_token(
            self.refresh_tokens, self.tokens, token.user_id, self.refresh_ttl_days
        )
        return access, refresh

    async def _handle_possible_reuse(
        self, token_hash: str, *, ip: str | None, user_agent: str | None
    ) -> None:
        """Reuse detection (OAuth 2.0 Security BCP): a token that was already
        rotated is being presented again, so two parties hold the same chain
        and we can't tell which is the thief — end every session of the user,
        including whatever descendants the other party minted.

        Only rotation-consumed tokens count. Tokens revoked by logout or a
        revoke-all (password change, admin action) are stale, not stolen —
        a second device waking up after a password change must not log out
        the device that changed it.
        """
        stale = await self.refresh_tokens.get_by_hash(token_hash)
        if not stale or not stale.replayed_after_rotation(grace=self.REUSE_GRACE):
            return
        await self.session_revoker.revoke_all_for_user(stale.user_id)
        await self.audit.record(
            AuditEvent(
                action=audit_actions.REFRESH_TOKEN_REUSED,
                actor_user_id=stale.user_id,
                ip=ip,
                user_agent=user_agent,
                meta={"all_sessions_revoked": True},
            )
        )


class LogoutUser:
    def __init__(self, refresh_tokens: RefreshTokenRepository, tokens: TokenService) -> None:
        self.refresh_tokens = refresh_tokens
        self.tokens = tokens

    async def execute(self, raw_token: str) -> None:
        token = await self.refresh_tokens.get_valid(self.tokens.hash_token(raw_token))
        if token:
            token.revoke()


class VerifyEmail:
    def __init__(
        self,
        users: UserRepository,
        tokens: TokenService,
        domain_org_joiner: DomainOrgJoiner | None = None,
    ) -> None:
        self.users = users
        self.tokens = tokens
        self.domain_org_joiner = domain_org_joiner

    async def execute(self, token: str) -> None:
        payload = self.tokens.decode_action_token(token, PURPOSE_VERIFY_EMAIL)
        user = payload and await self.users.get(uuid.UUID(payload["sub"]))
        if not user:
            raise InvalidActionToken("This verification link is invalid or has expired.")
        user.mark_email_verified()
        # Company-domain capture: a verified @claimed-domain address joins the
        # claiming org automatically. Idempotent, so repeat clicks are safe.
        if self.domain_org_joiner:
            await self.domain_org_joiner.execute(user)


class ResendVerification:
    def __init__(self, mailer: AuthMailer) -> None:
        self.mailer = mailer

    async def execute(self, user: User) -> None:
        if user.email_verified:
            return
        await self.mailer.send_verification(user)


class ForgotPassword:
    def __init__(self, users: UserRepository, tokens: TokenService, mailer: AuthMailer) -> None:
        self.users = users
        self.tokens = tokens
        self.mailer = mailer

    async def execute(self, email: str) -> None:
        """Always succeeds silently — never reveals whether the email exists."""
        user = await self.users.get_by_email(email)
        if not user or not user.is_active:
            return
        await self.mailer.send_password_reset(
            user, single_use_claims={"pwd": _password_fingerprint(self.tokens, user)}
        )


class ResetPassword:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        audit: AuditRecorder,
        mailer: AuthMailer,
        attempts: LoginAttemptTracker | None = None,
    ) -> None:
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.hasher = hasher
        self.tokens = tokens
        self.audit = audit
        self.mailer = mailer
        self.attempts = attempts

    async def execute(
        self,
        *,
        token: str,
        password: str,
        password_confirmation: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if password != password_confirmation:
            raise PasswordMismatch("Passwords do not match.")
        validate_password_strength(password)
        payload = self.tokens.decode_action_token(token, PURPOSE_PASSWORD_RESET)
        user = payload and await self.users.get(uuid.UUID(payload["sub"]))
        if not user or payload.get("pwd") != _password_fingerprint(self.tokens, user):
            raise InvalidActionToken("This reset link is invalid or has expired.")
        user.change_password(self.hasher.hash(password))
        user.mark_email_verified()  # the link proved control of the mailbox
        await self.refresh_tokens.revoke_all_for_user(user.id)
        if self.attempts:
            # The link proved mailbox control: lift any login lock so an owner
            # locked out by someone else's guessing can get straight back in.
            for lock_key in _lockout_keys(user.email, ip):
                await self.attempts.clear(lock_key)
        await self.audit.record(
            AuditEvent(
                action=audit_actions.PASSWORD_RESET,
                actor_user_id=user.id,
                ip=ip,
                user_agent=user_agent,
                meta={"all_sessions_revoked": True},
            )
        )
        await self.mailer.send_password_changed(user)


class SetMarketingOptIn:
    def __init__(self, marketing: MarketingList) -> None:
        self.marketing = marketing

    async def execute(self, user: User, opt_in: bool) -> User:
        """Toggle consent and sync the change to the marketing list provider."""
        if user.marketing_opt_in == opt_in:
            return user
        user.marketing_opt_in = opt_in
        if opt_in:
            await self.marketing.subscribe(user.email, user.first_name, user.last_name)
        else:
            await self.marketing.unsubscribe(user.email)
        return user


class UpdateProfile:
    def __init__(self, marketing: MarketingList) -> None:
        self.set_marketing_opt_in = SetMarketingOptIn(marketing)

    async def execute(
        self,
        user: User,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        marketing_opt_in: bool | None = None,
        analytics_opt_out: bool | None = None,
    ) -> User:
        """Partial profile update; only provided fields change."""
        if first_name is not None:
            user.first_name = first_name.strip()
        if last_name is not None:
            user.last_name = last_name.strip()
        if analytics_opt_out is not None:
            # Takes effect on the next event; past rows are kept (erasure is
            # the account-deletion / privacy-request path, not this toggle).
            user.analytics_opt_out = analytics_opt_out
        if marketing_opt_in is not None:
            await self.set_marketing_opt_in.execute(user, marketing_opt_in)
        return user


class ChangePassword:
    def __init__(
        self,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        refresh_ttl_days: int,
        audit: AuditRecorder,
        mailer: AuthMailer,
    ) -> None:
        self.refresh_tokens = refresh_tokens
        self.hasher = hasher
        self.tokens = tokens
        self.refresh_ttl_days = refresh_ttl_days
        self.audit = audit
        self.mailer = mailer

    async def execute(
        self,
        user: User,
        *,
        current_password: str,
        password: str,
        password_confirmation: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str]:
        """Change the password of a signed-in user.

        Requires the current password (a stolen access token must not be enough
        to take over the account). Every session is revoked, then a fresh one
        is issued so the caller stays signed in: returns
        (access_token, raw_refresh_token).
        """
        if not self.hasher.verify(current_password, user.password_hash):
            raise InvalidCredentials("Current password is incorrect.")
        if password != password_confirmation:
            raise PasswordMismatch("Passwords do not match.")
        validate_password_strength(password)
        user.change_password(self.hasher.hash(password))
        await self.refresh_tokens.revoke_all_for_user(user.id)
        access = self.tokens.create_access_token(str(user.id))
        refresh = await _issue_refresh_token(
            self.refresh_tokens, self.tokens, user.id, self.refresh_ttl_days
        )
        await self.audit.record(
            AuditEvent(
                action=audit_actions.PASSWORD_CHANGED,
                actor_user_id=user.id,
                ip=ip,
                user_agent=user_agent,
                meta={"all_sessions_revoked": True},
            )
        )
        await self.mailer.send_password_changed(user)
        return access, refresh


class PurgeExpiredRefreshTokens:
    """Delete refresh tokens long past expiry/revocation (beat-scheduled).

    Logins append a row per session and revocation only stamps `revoked_at`,
    so the table grows unboundedly without this. The grace window keeps
    recently dead tokens around for debugging ("why was I signed out?")."""

    GRACE = timedelta(days=30)

    def __init__(self, refresh_tokens: RefreshTokenRepository) -> None:
        self.refresh_tokens = refresh_tokens

    async def execute(self) -> int:
        return await self.refresh_tokens.delete_expired(now=datetime.now(UTC), grace=self.GRACE)
