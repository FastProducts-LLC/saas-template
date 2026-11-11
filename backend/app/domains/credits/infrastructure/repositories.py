"""Credits repositories.

Balance mutations go through a `FOR UPDATE` row lock on the wallet so
concurrent reserves can never overdraw it.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.api_keys.infrastructure.orm  # noqa: F401  (ApiKey mapping for ledger join)
import app.domains.auth.infrastructure.orm  # noqa: F401  (User mapping for ledger join)
import app.domains.credits.infrastructure.orm  # noqa: F401
import app.domains.organizations.infrastructure.orm  # noqa: F401  (Membership mapping)
from app.domains.api_keys.domain.entities import ApiKey
from app.domains.auth.domain import User
from app.domains.credits.application.dtos import UsageRow
from app.domains.credits.domain import (
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    MemberCreditLimit,
    ReservationStatus,
)
from app.domains.organizations.domain import Membership, Role

logger = logging.getLogger(__name__)

# Backstop for the usage GROUP BY: rows <= actors x actions, so hitting this
# means something pathological; log rather than silently truncate.
_USAGE_GROUP_LIMIT = 10_000


class SqlAlchemyWalletRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_org_locked(self, org_id: uuid.UUID) -> CreditWallet | None:
        stmt = select(CreditWallet).where(CreditWallet.organization_id == org_id).with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def add_if_absent(self, wallet: CreditWallet) -> bool:
        """Insert inside a savepoint. Returns False if unique(organization_id)
        rejects the row (a concurrent first-touch won the create race); the
        savepoint rollback keeps the surrounding transaction usable."""
        try:
            async with self.db.begin_nested():
                self.db.add(wallet)
                await self.db.flush()
        except IntegrityError:
            return False
        return True


class SqlAlchemyReservationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, reservation_id: uuid.UUID) -> CreditReservation | None:
        return await self.db.get(CreditReservation, reservation_id)

    async def get_locked(self, reservation_id: uuid.UUID) -> CreditReservation | None:
        stmt = (
            select(CreditReservation)
            .where(CreditReservation.id == reservation_id)
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_stale_pending(self, org_id: uuid.UUID, now: datetime) -> list[CreditReservation]:
        stmt = (
            select(CreditReservation)
            .where(
                CreditReservation.organization_id == org_id,
                CreditReservation.status == ReservationStatus.PENDING,
                CreditReservation.expires_at < now,
            )
            .with_for_update()
        )
        return list((await self.db.execute(stmt)).scalars())

    async def list_orgs_with_stale_pending(
        self, now: datetime, limit: int = 500
    ) -> list[uuid.UUID]:
        """Distinct orgs holding at least one expired pending reservation.
        No row locks — the per-org settle locks the wallet first."""
        stmt = (
            select(CreditReservation.organization_id)
            .where(
                CreditReservation.status == ReservationStatus.PENDING,
                CreditReservation.expires_at < now,
            )
            .distinct()
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars())

    async def list_pending(self, org_id: uuid.UUID) -> list[CreditReservation]:
        stmt = (
            select(CreditReservation)
            .where(
                CreditReservation.organization_id == org_id,
                CreditReservation.status == ReservationStatus.PENDING,
            )
            .order_by(CreditReservation.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars())

    async def add(self, reservation: CreditReservation) -> None:
        self.db.add(reservation)
        await self.db.flush()

    async def sum_active_for_user(
        self, org_id: uuid.UUID, user_id: uuid.UUID, since: datetime
    ) -> int:
        stmt = select(func.coalesce(func.sum(CreditReservation.amount), 0)).where(
            CreditReservation.organization_id == org_id,
            CreditReservation.user_id == user_id,
            CreditReservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CAPTURED]),
            CreditReservation.created_at >= since,
        )
        return (await self.db.execute(stmt)).scalar_one()


class SqlAlchemyLedgerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, tx: CreditTransaction) -> None:
        self.db.add(tx)

    async def add_idempotent(self, tx: CreditTransaction) -> bool:
        """Add + flush the row inside a savepoint. Returns False if its
        idempotency_key collides with the partial unique index (the row is
        rolled back), so a racing webhook redelivery is a safe no-op."""
        try:
            async with self.db.begin_nested():
                self.db.add(tx)
                await self.db.flush()
        except IntegrityError:
            return False
        return True

    async def exists_with_idempotency_key(self, key: str) -> bool:
        stmt = select(CreditTransaction.id).where(CreditTransaction.idempotency_key == key).limit(1)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def list_for_org(
        self, org_id: uuid.UUID, limit: int, offset: int
    ) -> list[tuple[CreditTransaction, str | None, str | None, ReservationStatus | None]]:
        """Ledger page, newest first, with the acting user's email, the acting
        API key's name, and the linked reservation's current status (so holds
        show as pending / finalized / refunded in history)."""
        stmt = (
            select(CreditTransaction, User.email, ApiKey.name, CreditReservation.status)
            .outerjoin(User, CreditTransaction.user_id == User.id)
            .outerjoin(ApiKey, CreditTransaction.api_key_id == ApiKey.id)
            .outerjoin(
                CreditReservation,
                CreditTransaction.reservation_id == CreditReservation.id,
            )
            .where(CreditTransaction.organization_id == org_id)
            .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [tuple(row) for row in (await self.db.execute(stmt)).all()]

    async def count_for_org(self, org_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(CreditTransaction)
            .where(CreditTransaction.organization_id == org_id)
        )
        return (await self.db.execute(stmt)).scalar_one()


class SqlAlchemyUsageRepository:
    """UsageReadRepository port — CAPTURED reservations grouped per actor."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def usage_by_actor(
        self, org_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[UsageRow]:
        count = func.count().label("count")
        credits = func.coalesce(func.sum(CreditReservation.amount), 0).label("credits")
        stmt = (
            select(
                CreditReservation.user_id,
                User.email,
                User.first_name,
                User.last_name,
                CreditReservation.api_key_id,
                ApiKey.name,
                CreditReservation.action,
                count,
                credits,
            )
            .outerjoin(User, CreditReservation.user_id == User.id)
            .outerjoin(ApiKey, CreditReservation.api_key_id == ApiKey.id)
            .where(
                CreditReservation.organization_id == org_id,
                CreditReservation.status == ReservationStatus.CAPTURED,
                CreditReservation.created_at >= start,
                CreditReservation.created_at < end,
            )
            .group_by(
                CreditReservation.user_id,
                User.email,
                User.first_name,
                User.last_name,
                CreditReservation.api_key_id,
                ApiKey.name,
                CreditReservation.action,
            )
            .limit(_USAGE_GROUP_LIMIT)
        )
        rows = (await self.db.execute(stmt)).all()
        if len(rows) == _USAGE_GROUP_LIMIT:
            logger.warning(
                "Usage rollup for org %s hit the %d group cap — results truncated",
                org_id,
                _USAGE_GROUP_LIMIT,
            )
        result: list[UsageRow] = []
        for user_id, email, first, last, api_key_id, key_name, action, cnt, total in rows:
            name = " ".join(p for p in (first, last) if p) or None
            result.append(
                UsageRow(
                    user_id=user_id,
                    user_email=email,
                    user_name=name,
                    api_key_id=api_key_id,
                    api_key_name=key_name,
                    action=action,
                    count=cnt,
                    credits=total,
                )
            )
        return result


class SqlAlchemyMemberLimitRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, org_id: uuid.UUID, user_id: uuid.UUID) -> MemberCreditLimit | None:
        stmt = select(MemberCreditLimit).where(
            MemberCreditLimit.organization_id == org_id,
            MemberCreditLimit.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def add(self, limit: MemberCreditLimit) -> None:
        self.db.add(limit)
        await self.db.flush()

    async def remove(self, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        limit = await self.get(org_id, user_id)
        if limit is None:
            return False
        await self.db.delete(limit)
        await self.db.flush()
        return True

    async def list_with_usage(
        self, org_id: uuid.UUID, since: datetime
    ) -> list[tuple[MemberCreditLimit, str | None, int]]:
        used = (
            select(func.coalesce(func.sum(CreditReservation.amount), 0))
            .where(
                CreditReservation.organization_id == org_id,
                CreditReservation.user_id == MemberCreditLimit.user_id,
                CreditReservation.status.in_(
                    [ReservationStatus.PENDING, ReservationStatus.CAPTURED]
                ),
                CreditReservation.created_at >= since,
            )
            .correlate(MemberCreditLimit)
            .scalar_subquery()
        )
        stmt = (
            select(MemberCreditLimit, User.email, used)
            .outerjoin(User, MemberCreditLimit.user_id == User.id)
            .where(MemberCreditLimit.organization_id == org_id)
            .order_by(User.email)
        )
        return [tuple(row) for row in (await self.db.execute(stmt)).all()]


class SqlAlchemyOrgOwnerEmails:
    """OrgOwnerEmails port → the emails of an org's OWNER members."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def owner_emails(self, org_id: uuid.UUID) -> list[str]:
        stmt = (
            select(User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.organization_id == org_id,
                Membership.role == Role.OWNER,
            )
        )
        return list((await self.db.execute(stmt)).scalars())
