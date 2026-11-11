"""Auth application ports — Protocols the use cases depend on.

Adapters live in `..infrastructure`; the composition root in
`..interface.deps` wires them in. Tests substitute in-memory fakes.
"""

import uuid
from datetime import datetime, timedelta
from typing import Protocol

from app.domains.audit.domain import AuditEvent
from app.domains.auth.domain import RefreshToken, User


class UserRepository(Protocol):
    async def get(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, user: User) -> None: ...


class RefreshTokenRepository(Protocol):
    async def get_valid(self, token_hash: str) -> RefreshToken | None: ...

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """The token in any state (revoked/expired included) — reuse detection."""
        ...

    async def add(self, token: RefreshToken) -> None: ...

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Kill every active session (e.g. after a password reset)."""
        ...

    async def delete_expired(self, *, now: datetime, grace: timedelta) -> int:
        """Purge tokens expired or revoked for longer than `grace`. They are
        already unusable — this only bounds table growth."""
        ...


class SessionRevoker(Protocol):
    """Kills every active session of a user in its OWN transaction, so the
    revocation survives the rollback that raising SessionExpired triggers."""

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    """Access-token minting and action-token (email link) validation."""

    def create_access_token(self, user_id: str) -> str: ...

    def new_opaque_token(self) -> tuple[str, str]:
        """Return (raw_token, hash). Only the hash is ever stored."""
        ...

    def hash_token(self, raw: str) -> str: ...

    def decode_action_token(self, token: str, purpose: str) -> dict | None: ...


class AuthMailer(Protocol):
    """Transactional auth email. Owns link construction (tokens, frontend
    URLs) so use cases stay config-free. All sends are best-effort."""

    async def send_welcome_with_verification(self, user: User) -> None: ...

    async def send_verification(self, user: User) -> None: ...

    async def send_account_exists_notice(self, user: User) -> None:
        """Verify-first signup: someone tried to register an address that
        already has an account. The owner is told by email; the HTTP response
        says nothing."""
        ...

    async def send_password_reset(self, user: User, single_use_claims: dict) -> None: ...

    async def send_password_changed(self, user: User) -> None:
        """Security notice after a successful change or reset — the owner
        hears about it even if someone else did it."""
        ...


class DomainOrgJoiner(Protocol):
    """Joins the user to the organization that claimed their email domain,
    if any. Satisfied structurally by organizations' AutoJoinByEmailDomain —
    auth stays ignorant of orgs internals."""

    async def execute(self, user: User) -> object | None: ...


class LoginAttemptTracker(Protocol):
    """Consecutive-failure lockout over opaque string keys. LoginUser tracks
    two per attempt — normalized email + client IP, and the email alone (see
    its docstring). A key may not correspond to an account — tracking unknown
    emails identically is what keeps lockout responses enumeration-safe. The
    Redis adapter degrades to an in-memory tracker when Redis is unreachable."""

    async def lockout_remaining(self, key: str) -> int:
        """Seconds left on an active lock; 0 when not locked."""
        ...

    async def record_failure(self, key: str) -> int:
        """Count this failure; returns consecutive failures including it."""
        ...

    async def lock(self, key: str) -> None: ...

    async def clear(self, key: str) -> None: ...


class AuditRecorder(Protocol):
    """Security-event trail. Satisfied structurally by the audit slice's
    AutonomousAuditRecorder; writes are best-effort and never raise."""

    async def record(self, event: AuditEvent) -> None: ...


class MarketingList(Protocol):
    """Marketing contact sync. GDPR: callers only invoke subscribe for users
    who explicitly opted in — never by default."""

    async def subscribe(self, email: str, first_name: str, last_name: str) -> None: ...

    async def unsubscribe(self, email: str) -> None: ...
