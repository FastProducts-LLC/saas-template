"""Auth repositories — SQLAlchemy implementations of the application ports.

Imperative mapping means queries return the pure domain entities directly
(change-tracked by the session), so there is no ORM↔entity translation.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.auth.infrastructure.orm  # noqa: F401  (attaches the mapping)
from app.domains.auth.domain import RefreshToken, User


class SqlAlchemyUserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def add(self, user: User) -> None:
        self.db.add(user)
        await self.db.flush()


class SqlAlchemyMarketingPreferencesRepository:
    """Writes marketing/deliverability flags on the auth-owned `users` table.

    Auth owns `users`; other slices (e.g. emails' webhook processing) consume
    this through `build_marketing_preferences_repository` in `..interface.deps`
    and their own structural ports.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def set_marketing_opt_out(self, email: str) -> bool:
        """Flip marketing_opt_in off for the matching user. Returns True if found."""
        stmt = (
            update(User)
            .where(func.lower(User.email) == email.lower())
            .values(marketing_opt_in=False)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def is_email_suppressed(self, email: str) -> bool:
        """True if a user with this address is flagged undeliverable. Unknown
        addresses (e.g. an invitee with no account) are not suppressed."""
        stmt = select(User.id).where(
            func.lower(User.email) == email.lower(), User.email_suppressed.is_(True)
        )
        return (await self.db.execute(stmt.limit(1))).first() is not None

    async def suppress_email(self, email: str) -> bool:
        """Mark the matching user's address as undeliverable (hard bounce /
        spam complaint). Returns True if found."""
        stmt = (
            update(User)
            .where(func.lower(User.email) == email.lower())
            .values(email_suppressed=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def suppress_and_opt_out(self, email: str) -> bool:
        """Suppress the address AND revoke marketing opt-in in a single
        UPDATE (spam-complaint path). Returns True if found."""
        stmt = (
            update(User)
            .where(func.lower(User.email) == email.lower())
            .values(email_suppressed=True, marketing_opt_in=False)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_valid(self, token_hash: str) -> RefreshToken | None:
        # FOR UPDATE serializes concurrent rotations of the same refresh token:
        # the second request blocks until the first commits its revoke, then
        # re-evaluates `revoked_at IS NULL` and finds the row gone (returns
        # None -> SessionExpired). Without the lock both requests pass the check
        # and both mint fresh tokens.
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def add(self, token: RefreshToken) -> None:
        self.db.add(token)
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Kill every active session (e.g. after a password reset)."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.execute(stmt)

    async def delete_expired(self, *, now: datetime, grace: timedelta) -> int:
        """Purge tokens expired or revoked for longer than `grace`. They are
        already unusable — this only bounds table growth."""
        cutoff = now - grace
        stmt = delete(RefreshToken).where(
            or_(RefreshToken.expires_at < cutoff, RefreshToken.revoked_at < cutoff)
        )
        result = await self.db.execute(stmt)
        return result.rowcount or 0
