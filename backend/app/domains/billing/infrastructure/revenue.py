"""SQL read model for platform revenue; no ORM entities or writes."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.billing.application.revenue import (
    LIVE_STATUSES,
    RevenueGroup,
    RevenueSubscription,
)
from app.domains.billing.domain.value_objects import PlanSubscriptionStatus
from app.domains.billing.infrastructure.orm import subscriptions_table


class SqlAlchemyRevenueReader:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def grouped_revenue(self, now: datetime) -> list[RevenueGroup]:
        c = subscriptions_table.c
        cutoff = now - timedelta(days=30)
        live = c.status.in_(LIVE_STATUSES)
        stmt = select(
            c.plan,
            c.interval,
            c.status,
            func.count().label("count"),
            func.count().filter(live, c.cancel_at_period_end.is_(True)).label("canceling"),
            func.count()
            .filter(live, c.created_at >= cutoff, c.created_at <= now)
            .label("new_last_30d"),
            func.count()
            .filter(
                c.status == PlanSubscriptionStatus.CANCELED,
                c.updated_at >= cutoff,
                c.updated_at <= now,
            )
            .label("canceled_last_30d"),
        ).group_by(c.plan, c.interval, c.status)
        with self.db.no_autoflush:
            rows = (await self.db.execute(stmt)).mappings().all()
        return [RevenueGroup(**row) for row in rows]

    async def list_subscriptions(self) -> list[RevenueSubscription]:
        c = subscriptions_table.c
        with self.db.no_autoflush:
            rows = (
                (
                    await self.db.execute(
                        select(
                            c.stripe_subscription_id.label("subscription_id"),
                            c.organization_id.label("org_id"),
                            c.plan,
                            c.interval,
                            c.status,
                        )
                    )
                )
                .mappings()
                .all()
            )
        return [RevenueSubscription(**row) for row in rows]
