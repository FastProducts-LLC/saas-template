"""Revenue SQL aggregation, HTTP authorization, and read-only reconciliation."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from sqlalchemy import event, insert, select

from app.domains.billing.application.dtos import SubscriptionSnapshot
from app.domains.billing.application.ports import RevenueGateway
from app.domains.billing.application.revenue import GetRevenue, ReconcileRevenue
from app.domains.billing.domain.value_objects import (
    PLANS,
    Plan,
)
from app.domains.billing.domain.value_objects import (
    BillingInterval as Interval,
)
from app.domains.billing.domain.value_objects import (
    PlanSubscriptionStatus as Status,
)
from app.domains.billing.infrastructure.orm import subscriptions_table
from app.domains.billing.infrastructure.revenue import SqlAlchemyRevenueReader
from app.domains.organizations.domain import Organization
from tests.helpers import make_superuser, register_and_login


async def seed(
    db,
    *,
    plan=Plan.PRO,
    interval=Interval.MONTHLY,
    status=Status.ACTIVE,
    canceling=False,
    created_at=None,
    updated_at=None,
):
    org = Organization(name="Revenue test", slug=str(uuid.uuid4()))
    db.add(org)
    await db.flush()
    now = datetime.now(UTC)
    subscription_id = f"sub_{uuid.uuid4().hex}"
    await db.execute(
        insert(subscriptions_table).values(
            id=uuid.uuid4(),
            organization_id=org.id,
            stripe_subscription_id=subscription_id,
            plan=plan,
            interval=interval,
            status=status,
            cancel_at_period_end=canceling,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )
    )
    return SubscriptionSnapshot(
        subscription_id, org.id, None, plan, interval, status, None, canceling, True
    )


async def revenue(db, **kwargs):
    return await GetRevenue(SqlAlchemyRevenueReader(db)).execute(**kwargs)


def reconciler(db, snapshots):
    gateway = AsyncMock(spec=RevenueGateway)
    gateway.list_org_plan_subscriptions.return_value = snapshots
    return ReconcileRevenue(SqlAlchemyRevenueReader(db), gateway), gateway


async def test_revenue_empty_is_zero(db):
    result = await revenue(db)
    assert result.currency == "usd"
    assert (
        result.mrr_cents,
        result.arr_cents,
        result.active,
        result.trialing,
        result.past_due,
        result.canceling,
        result.new_last_30d,
        result.canceled_last_30d,
    ) == (0,) * 8
    assert all(row.count == row.mrr_cents == 0 for row in result.by_plan)
    assert result.computed_at.tzinfo is not None


async def test_revenue_mrr_counts_active_monthly_and_annual(db):
    await seed(db)
    await seed(db, interval=Interval.ANNUAL, plan=Plan.TEAM)
    result = await revenue(db)
    assert result.mrr_cents == 11150
    assert result.arr_cents == 133800
    assert result.active == 2


async def test_revenue_annual_division_rounds_once_at_the_end(db, monkeypatch):
    for _ in range(3):
        await seed(db, interval=Interval.ANNUAL)
    # Three annual subscriptions: 3 * 29000 / 12 = 7250, not 3 * 2417.
    assert (await revenue(db)).mrr_cents == 7250
    # Half-cent ties and independent display rounding across plan groups.
    monkeypatch.setitem(PLANS, Plan.PRO, replace(PLANS[Plan.PRO], annual_price_cents=2))
    assert (await revenue(db)).mrr_cents == 1  # 3 * 2/12 = 0.5, half up
    monkeypatch.setitem(PLANS, Plan.PRO, replace(PLANS[Plan.PRO], annual_price_cents=1))
    monkeypatch.setitem(PLANS, Plan.TEAM, replace(PLANS[Plan.TEAM], annual_price_cents=3))
    await seed(db, plan=Plan.TEAM, interval=Interval.ANNUAL)
    result = await revenue(db)
    assert result.mrr_cents == 1
    assert sum(row.mrr_cents for row in result.by_plan) == 0


async def test_revenue_counts_past_due_in_mrr(db):
    await seed(db, status=Status.PAST_DUE)
    result = await revenue(db)
    assert result.mrr_cents == PLANS[Plan.PRO].monthly_price_cents
    assert result.past_due == 1
    assert result.active == 0


async def test_revenue_excludes_trialing_canceled_and_incomplete_from_mrr(db):
    for status in (Status.TRIALING, Status.CANCELED, Status.INCOMPLETE):
        await seed(db, status=status)
    result = await revenue(db)
    assert result.mrr_cents == result.arr_cents == 0
    assert result.trialing == 1
    assert result.active == result.past_due == 0


async def test_revenue_counts_canceling_separately_but_keeps_mrr(db):
    for status in Status:
        await seed(db, status=status, canceling=True)
    result = await revenue(db)
    assert result.canceling == 3
    assert result.mrr_cents == 2 * PLANS[Plan.PRO].monthly_price_cents


async def test_revenue_by_plan_lists_every_paid_plan_and_interval(db):
    await seed(db, interval=Interval.ANNUAL)
    result = await revenue(db)
    assert [(r.plan, r.interval) for r in result.by_plan] == [
        (plan, interval) for plan in PLANS if plan != Plan.FREE for interval in Interval
    ]
    for row in result.by_plan:
        if (row.plan, row.interval) == (Plan.PRO, Interval.ANNUAL):
            assert (row.count, row.mrr_cents) == (1, 2417)
        else:
            assert (row.count, row.mrr_cents) == (0, 0)


async def test_revenue_new_and_canceled_windows(db):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    for status in Status:
        for when in (cutoff, cutoff - timedelta(microseconds=1), now + timedelta(days=1)):
            await seed(db, status=status, created_at=when, updated_at=when)
    result = await revenue(db, now=now)
    assert result.new_last_30d == 3
    assert result.canceled_last_30d == 1


async def test_revenue_requires_superuser(client, db):
    assert (await client.get("/api/admin/revenue")).status_code == 401
    user, headers = await register_and_login(client, "revenue@example.com")
    assert (await client.get("/api/admin/revenue", headers=headers)).status_code == 403
    await make_superuser(db, user["id"])
    await seed(db)
    await db.commit()
    response = await client.get("/api/admin/revenue", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["mrr_cents"] == PLANS[Plan.PRO].monthly_price_cents
    assert response.json()["computed_at"]


async def test_reconcile_in_sync(db):
    snapshots = [await seed(db, interval=Interval.ANNUAL) for _ in range(3)]
    snapshots.append(await seed(db, status=Status.TRIALING))
    snapshots.append(await seed(db, status=Status.PAST_DUE))
    use_case, gateway = reconciler(db, snapshots)
    result = await use_case.execute()
    assert result.in_sync and result.drift == []
    assert result.local_mrr_cents == result.stripe_mrr_cents == 10150
    gateway.list_org_plan_subscriptions.assert_awaited_once_with()


async def test_reconcile_detects_status_plan_and_interval_mismatch(db):
    snapshot = await seed(db, status=Status.TRIALING)
    remote = replace(snapshot, status=Status.PAST_DUE, plan=Plan.TEAM, interval=Interval.ANNUAL)
    use_case, _ = reconciler(db, [remote])
    result = await use_case.execute()
    assert not result.in_sync
    assert {d.kind for d in result.drift} == {
        "status_mismatch",
        "plan_mismatch",
        "interval_mismatch",
    }
    assert all(
        d.subscription_id == snapshot.subscription_id and d.org_id == snapshot.org_id
        for d in result.drift
    )
    assert result.local_mrr_cents == 0
    assert result.stripe_mrr_cents == 8250


async def test_reconcile_detects_missing_on_either_side(db):
    local = await seed(db)
    remote = replace(local, subscription_id="sub_remote", org_id=uuid.uuid4())
    use_case, _ = reconciler(db, [remote])
    result = await use_case.execute()
    assert not result.in_sync
    assert {(d.kind, d.subscription_id) for d in result.drift} == {
        ("missing_locally", "sub_remote"),
        ("missing_in_stripe", local.subscription_id),
    }
    assert result.local_mrr_cents == result.stripe_mrr_cents


async def test_reconcile_ignores_subscriptions_canceled_on_both_sides(db):
    snapshot = await seed(db, status=Status.CANCELED)
    await seed(db, status=Status.CANCELED)  # Also ignore local ended rows absent in Stripe.
    use_case, _ = reconciler(
        db,
        [
            replace(snapshot, plan=Plan.TEAM, interval=Interval.ANNUAL),
            replace(snapshot, subscription_id="sub_ended_remote"),
        ],
    )
    result = await use_case.execute()
    assert result.in_sync and result.drift == []
    assert result.local_mrr_cents == result.stripe_mrr_cents == 0


async def test_reconcile_makes_no_writes(db):
    snapshot = await seed(db)
    await db.commit()
    before = (await db.execute(select(subscriptions_table))).all()
    use_case, gateway = reconciler(db, [replace(snapshot, plan=Plan.TEAM)])
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db.bind.sync_engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        result = await use_case.execute()
        await revenue(db)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert not result.in_sync
    assert statements and all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    assert not db.new and not db.dirty and not db.deleted
    assert (await db.execute(select(subscriptions_table))).all() == before
    assert [call[0] for call in gateway.mock_calls] == ["list_org_plan_subscriptions"]


async def test_gateway_lists_all_pages_and_reuses_snapshot_mapping(monkeypatch):
    from app.domains.billing.infrastructure import stripe_gateway as module

    gateway = module.StripeGateway()
    monkeypatch.setattr(module.settings, "stripe_price_plan_pro_monthly", "price_pro")
    calls = []

    async def stripe_call(fn, *args, **kwargs):
        calls.append((fn, args, kwargs))
        if fn == module.stripe.Subscription.list:
            if "starting_after" not in kwargs:
                return {
                    "data": [
                        {"id": "sub_org", "metadata": {"org_plan": "1"}},
                        {"id": "sub_community", "metadata": {"community_membership": "1"}},
                    ],
                    "has_more": True,
                }
            return {
                "data": [{"id": "sub_canceled", "metadata": {"org_plan": "1"}}],
                "has_more": False,
            }
        assert fn == module.stripe.Subscription.retrieve
        return {
            "id": args[0],
            "metadata": {"org_plan": "1"},
            "status": "active" if args[0] == "sub_org" else "canceled",
            "items": {"data": [{"price": {"id": "price_pro"}}]},
        }

    monkeypatch.setattr(module, "_stripe_call", stripe_call)
    snapshots = await gateway.list_org_plan_subscriptions()
    assert [s.status for s in snapshots] == [Status.ACTIVE, Status.CANCELED]
    assert all(s.plan == Plan.PRO and s.interval == Interval.MONTHLY for s in snapshots)
    pages = [kwargs for fn, _, kwargs in calls if fn == module.stripe.Subscription.list]
    assert pages == [
        {"status": "all", "limit": 100},
        {"status": "all", "limit": 100, "starting_after": "sub_community"},
    ]
