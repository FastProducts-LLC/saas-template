"""Auth domain entities — pure Python, zero framework/ORM imports.

These dataclasses are mapped to tables in `..infrastructure.orm` via
SQLAlchemy imperative mapping, so instances loaded through a repository are
change-tracked; mutating an entity inside a request transaction persists it.
The classes themselves know nothing about that.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(eq=False)
class User:
    email: str
    password_hash: str
    first_name: str
    last_name: str = ""
    is_active: bool = True
    # Platform-level (cross-tenant) admin. No API grants this; flip it
    # manually in the database: UPDATE users SET is_superuser = true WHERE ...
    is_superuser: bool = False
    marketing_opt_in: bool = False
    # Hard bounce or spam complaint (set via the Resend webhook) — the address
    # is dead or hostile; skip all email, transactional included.
    email_suppressed: bool = False
    # GDPR Art. 21 objection to product analytics: while set, nothing is
    # written to activity_events for this user (client or server events) and
    # the web client disables GA for them. Toggled from Profile.
    analytics_opt_out: bool = False
    terms_accepted_at: datetime | None = None
    # Set when the user proves control of the mailbox (activation link or
    # password reset). Enforcement is env-driven via EMAIL_VERIFICATION_GATE
    # (none | sensitive | login) — see CurrentVerifiedUser / LoginUser.
    email_verified_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    @classmethod
    def register(
        cls,
        *,
        email: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        marketing_opt_in: bool,
    ) -> "User":
        """Factory enforcing registration invariants: consent is timestamped
        at birth, names are normalized, email is canonical lowercase."""
        return cls(
            email=email.lower(),
            password_hash=password_hash,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            marketing_opt_in=marketing_opt_in,
            terms_accepted_at=_utcnow(),
        )

    @property
    def name(self) -> str:
        """Full display name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    def mark_email_verified(self) -> None:
        """Idempotent — keeps the original verification timestamp."""
        if self.email_verified_at is None:
            self.email_verified_at = _utcnow()

    def change_password(self, new_password_hash: str) -> None:
        self.password_hash = new_password_hash


@dataclass(eq=False)
class RefreshToken:
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    # Set only when the token was consumed by a rotation (not by logout or a
    # revoke-all). A later replay of such a token means two parties hold the
    # same chain — the theft signal RefreshSession acts on.
    rotated_at: datetime | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def revoke(self) -> None:
        self.revoked_at = _utcnow()

    def rotate(self) -> None:
        """Revoke as part of a rotation (a successor token is being issued)."""
        now = _utcnow()
        self.revoked_at = now
        self.rotated_at = now

    def replayed_after_rotation(self, *, grace: timedelta, now: datetime | None = None) -> bool:
        """True when presenting this token again indicates reuse. Replays
        inside `grace` are the benign rotation race (two tabs / a retried
        request racing on the same token) and are merely rejected."""
        if self.rotated_at is None:
            return False
        return (now or _utcnow()) - self.rotated_at > grace
