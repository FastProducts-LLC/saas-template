"""Plan-aware lazy grants and upgrade top-ups using the real credit engine."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select

import app.domains.credits.application.use_cases as credit_cases
from app.domains.billing.application.dtos import OrgSubscriptionChanged, SubscriptionSnapshot
from app.domains.billing.application.plans import ApplyOrgSubscriptionEvent
from app.domains.billing.domain.value_objects import (
    PLANS,
    BillingInterval,
    Plan,
    PlanSubscriptionStatus,
)
from app.domains.billing.infrastructure.repositories import SqlAlchemySubscriptionRepository
from app.domains.credits.domain import MONTHLY_ALLOWANCE_CREDITS, CreditTransaction, CreditWallet
from app.domains.credits.interface.deps import build_credit_engine
from app.domains.organizations.infrastructure.repositories import SqlAlchemyOrgRepository
from tests.helpers import create_org, register_and_login
from tests.test_billing_plans import seed_subscription


@pytest_asyncio.fixture
async def allowance_context(client, db):
    user, headers = await register_and_login(client)
    org = await create_org(client, headers)
    return SimpleNamespace(
        org_id=uuid.UUID(org["id"]),
        user_id=uuid.UUID(user["id"]),
        engine=build_credit_engine(db),
    )


async def change_plan(db, ctx, plan, status=PlanSubscriptionStatus.ACTIVE):
    snapshot = SubscriptionSnapshot(
        subscription_id="sub_plan",
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        plan=plan,
        interval=BillingInterval.MONTHLY,
        status=status,
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        cancel_at_period_end=False,
        is_org_plan=True,
    )
    handler = ApplyOrgSubscriptionEvent(
        subscriptions=SqlAlchemySubscriptionRepository(db),
        organizations=SqlAlchemyOrgRepository(db),
        gateway=SimpleNamespace(fetch_subscription=AsyncMock(return_value=snapshot)),
        credits=ctx.engine,
    )
    await handler.execute(OrgSubscriptionChanged("sub_plan", ctx.org_id))
    await db.flush()


async def ledger(db, ctx):
    return list(
        (
            await db.scalars(
                select(CreditTransaction).where(
                    CreditTransaction.organization_id == ctx.org_id,
                )
            )
        ).all()
    )


async def test_free_org_uses_default_allowance(db, allowance_context, monkeypatch):
    ctx = allowance_context
    # Keep the existing call-time patch point working, even with the reader wired.
    monkeypatch.setattr(credit_cases, "MONTHLY_ALLOWANCE_CREDITS", 37)
    wallet = await ctx.engine.settle(ctx.org_id)
    assert wallet.balance == 37
    entries = await ledger(db, ctx)
    assert [entry.amount for entry in entries] == [37]


async def test_paid_org_gets_plan_allowance_on_first_touch_of_month(db, allowance_context):
    ctx = allowance_context
    await seed_subscription(db, ctx.org_id, plan=Plan.TEAM)
    db.add(CreditWallet(organization_id=ctx.org_id, balance=17, allowance_period="2000-01"))
    await db.flush()
    wallet = await ctx.engine.settle(ctx.org_id)
    assert wallet.balance == 17 + PLANS[Plan.TEAM].monthly_credits
    assert [entry.amount for entry in await ledger(db, ctx)] == [PLANS[Plan.TEAM].monthly_credits]


async def test_allowance_not_granted_twice_in_same_month(db, allowance_context):
    ctx = allowance_context
    await seed_subscription(db, ctx.org_id)
    wallet = await ctx.engine.settle(ctx.org_id)
    await ctx.engine.settle(ctx.org_id)
    assert wallet.balance == PLANS[Plan.PRO].monthly_credits
    assert len(await ledger(db, ctx)) == 1


async def test_upgrade_mid_month_tops_up_difference_once(db, allowance_context):
    ctx = allowance_context
    wallet = await ctx.engine.settle(ctx.org_id)
    assert wallet.balance == MONTHLY_ALLOWANCE_CREDITS
    await change_plan(db, ctx, Plan.PRO)
    await change_plan(db, ctx, Plan.PRO)
    assert wallet.balance == PLANS[Plan.PRO].monthly_credits
    entries = await ledger(db, ctx)
    topups = [entry for entry in entries if entry.idempotency_key]
    assert len(topups) == 1
    assert topups[0].amount == PLANS[Plan.PRO].monthly_credits - MONTHLY_ALLOWANCE_CREDITS
    assert topups[0].idempotency_key == f"plan-topup:{ctx.org_id}:{datetime.now(UTC):%Y-%m}:pro"
    await change_plan(db, ctx, Plan.TEAM)
    await change_plan(db, ctx, Plan.TEAM)
    assert wallet.balance == PLANS[Plan.TEAM].monthly_credits
    assert sum(entry.amount for entry in await ledger(db, ctx)) == wallet.balance


async def test_upgrade_before_first_touch_grants_full_allowance_only(db, allowance_context):
    ctx = allowance_context
    await change_plan(db, ctx, Plan.PRO)
    wallet = await ctx.engine.settle(ctx.org_id)
    assert wallet.balance == PLANS[Plan.PRO].monthly_credits
    entries = await ledger(db, ctx)
    assert sum(entry.amount for entry in entries) == PLANS[Plan.PRO].monthly_credits
    assert len([entry for entry in entries if entry.amount > 0]) == 1
    assert [entry.amount for entry in entries if entry.idempotency_key] == [0]


async def test_downgrade_does_not_claw_back(db, allowance_context):
    ctx = allowance_context
    await change_plan(db, ctx, Plan.TEAM)
    wallet = await ctx.engine.settle(ctx.org_id)
    before = wallet.balance
    await change_plan(db, ctx, Plan.PRO)
    await change_plan(db, ctx, Plan.PRO, PlanSubscriptionStatus.CANCELED)
    assert wallet.balance == before == PLANS[Plan.TEAM].monthly_credits
    assert all(entry.amount >= 0 for entry in await ledger(db, ctx))


@pytest.mark.parametrize("touch_first", [True, False])
async def test_resubscribe_same_month_does_not_top_up_again(db, allowance_context, touch_first):
    ctx = allowance_context
    if touch_first:
        await ctx.engine.settle(ctx.org_id)
    await change_plan(db, ctx, Plan.PRO)
    wallet = await ctx.engine.settle(ctx.org_id)
    before = wallet.balance
    await change_plan(db, ctx, Plan.PRO, PlanSubscriptionStatus.CANCELED)
    await change_plan(db, ctx, Plan.PRO)
    assert wallet.balance == before == PLANS[Plan.PRO].monthly_credits
    entries = await ledger(db, ctx)
    assert len([entry for entry in entries if entry.idempotency_key]) == 1


async def test_top_up_returns_granted_difference(db, allowance_context):
    ctx = allowance_context
    await ctx.engine.settle(ctx.org_id)
    granted = await ctx.engine.top_up_plan_allowance(
        ctx.org_id,
        previous_allowance=MONTHLY_ALLOWANCE_CREDITS,
        new_allowance=PLANS[Plan.PRO].monthly_credits,
        idempotency_key="direct-topup",
    )
    assert granted == PLANS[Plan.PRO].monthly_credits - MONTHLY_ALLOWANCE_CREDITS
    assert (
        await ctx.engine.top_up_plan_allowance(
            ctx.org_id,
            previous_allowance=MONTHLY_ALLOWANCE_CREDITS,
            new_allowance=PLANS[Plan.PRO].monthly_credits,
            idempotency_key="direct-topup",
        )
        == 0
    )


async def test_zero_marker_and_real_top_up_have_distinct_descriptions(db, allowance_context):
    ctx = allowance_context
    await change_plan(db, ctx, Plan.PRO)
    await change_plan(db, ctx, Plan.TEAM)
    entries = [entry for entry in await ledger(db, ctx) if entry.idempotency_key]
    assert len(entries) == 2
    marker = next(entry for entry in entries if entry.amount == 0)
    top_up = next(entry for entry in entries if entry.amount > 0)
    assert marker.description == "Plan allowance for this month already applied"
    assert top_up.description == "Plan-upgrade top-up"
    assert top_up.amount == PLANS[Plan.TEAM].monthly_credits - PLANS[Plan.PRO].monthly_credits
    assert marker.idempotency_key.endswith(":pro")
    assert top_up.idempotency_key.endswith(":team")
