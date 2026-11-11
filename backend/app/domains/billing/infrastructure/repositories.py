"""Billing repository — billing-account persistence."""

import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.domains.billing.infrastructure.orm  # noqa: F401
from app.domains.billing.domain import BillingAccount
from app.domains.billing.domain.entities import Subscription


class SqlAlchemyBillingAccountRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_org(self, org_id: uuid.UUID) -> BillingAccount | None:
        stmt = select(BillingAccount).where(BillingAccount.organization_id == org_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def add(self, account: BillingAccount) -> None:
        self.db.add(account)
        await self.db.flush()


class SqlAlchemySubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_for_org(self, org_id: uuid.UUID) -> Subscription | None:
        return (
            await self.db.execute(
                select(Subscription).where(Subscription.organization_id == org_id)
            )
        ).scalar_one_or_none()

    async def get_for_org_locked(self, org_id: uuid.UUID) -> Subscription | None:
        # A row lock alone cannot serialize two first-ever webhook deliveries.
        # The transaction advisory lock also protects the absent-row case without
        # locking the organization (audit writes use an autonomous FK transaction).
        key = int.from_bytes(
            hashlib.sha256(f"org-subscription:{org_id}".encode()).digest()[:8],
            byteorder="big",
            signed=True,
        )
        await self.db.execute(select(func.pg_advisory_xact_lock(key)))
        return (
            await self.db.execute(
                select(Subscription)
                .where(Subscription.organization_id == org_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def get_by_stripe_id(self, subscription_id: str) -> Subscription | None:
        return (
            await self.db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
            )
        ).scalar_one_or_none()

    async def add(self, subscription: Subscription) -> None:
        self.db.add(subscription)
        await self.db.flush()
