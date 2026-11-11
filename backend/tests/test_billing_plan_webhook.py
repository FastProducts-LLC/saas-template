"""Org subscription webhooks use fetched Stripe state and isolate community billing."""

import asyncio
import tomllib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
import stripe
from sqlalchemy import select

from app.core.config import settings
from app.core.policy import BILLING_PLAN_GRACE_DAYS
from app.domains.analytics.domain import ActivityEvent
from app.domains.audit.domain import AuditEvent, actions
from app.domains.billing.application.dtos import SubscriptionSnapshot
from app.domains.billing.domain.entities import Subscription
from app.domains.billing.domain.value_objects import (
    PLANS,
    BillingInterval,
    Plan,
    PlanSubscriptionStatus,
)
from app.domains.billing.infrastructure.stripe_gateway import StripeGateway
from app.domains.billing.interface.deps import build_plan_reader
from app.domains.community.domain import CommunityMembership, MembershipTier, SubscriptionStatus
from app.domains.credits.domain import MONTHLY_ALLOWANCE_CREDITS, CreditTransaction, CreditWallet
from tests.helpers import create_org, register_and_login
from tests.test_billing import WEBHOOK_SECRET, _event, _post_webhook
from tests.test_billing_plans import seed_subscription


@pytest_asyncio.fixture
async def webhook_context(client, monkeypatch):
    user, headers = await register_and_login(client)
    org = await create_org(client, headers)
    ctx = SimpleNamespace(
        user_id=uuid.UUID(user["id"]),
        org_id=uuid.UUID(org["id"]),
        headers=headers,
        fetches=[],
    )
    ctx.snapshot = SubscriptionSnapshot(
        subscription_id="sub_plan",
        org_id=ctx.org_id,
        user_id=ctx.user_id,
        plan=Plan.PRO,
        interval=BillingInterval.MONTHLY,
        status=PlanSubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        cancel_at_period_end=False,
        is_org_plan=True,
    )

    async def fetch(self, subscription_id):
        ctx.fetches.append(subscription_id)
        return ctx.snapshot

    monkeypatch.setattr(StripeGateway, "fetch_subscription", fetch)
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)
    return ctx


async def post_plan(client, ctx, etype="customer.subscription.updated", **overrides):
    obj = {
        "id": ctx.snapshot.subscription_id if ctx.snapshot else "sub_missing",
        "status": "active",
        "metadata": {"org_plan": "1", "organization_id": str(ctx.org_id)},
    }
    if etype == "checkout.session.completed":
        obj.update(id="cs_plan", mode="subscription", subscription=ctx.snapshot.subscription_id)
    obj.update(overrides)
    response = await _post_webhook(client, _event(etype, obj))
    assert response.status_code == 200, response.text
    return response


async def subscription(db, org_id):
    return await db.scalar(
        select(Subscription)
        .where(
            Subscription.organization_id == org_id,
        )
        .execution_options(populate_existing=True)
    )


async def audits(db, ctx, action):
    return list(
        (
            await db.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == ctx.org_id,
                    AuditEvent.action == action,
                )
            )
        ).all()
    )


async def activity(db, ctx, event):
    return list(
        (
            await db.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.user_id == ctx.user_id,
                    ActivityEvent.event == event,
                )
            )
        ).all()
    )


async def test_checkout_completed_creates_subscription(client, db, webhook_context):
    ctx = webhook_context
    await post_plan(client, ctx, "checkout.session.completed")
    row = await subscription(db, ctx.org_id)
    assert row.stripe_subscription_id == "sub_plan"
    assert row.plan == Plan.PRO
    assert row.status == PlanSubscriptionStatus.ACTIVE
    assert row.current_period_end == ctx.snapshot.current_period_end
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.PRO


async def test_duplicate_event_is_idempotent(client, db, webhook_context):
    ctx = webhook_context
    await post_plan(client, ctx, "checkout.session.completed")
    await post_plan(client, ctx, "checkout.session.completed")
    assert len((await db.scalars(select(Subscription))).all()) == 1
    assert len(await audits(db, ctx, actions.PLAN_SUBSCRIBED)) == 1
    events = await activity(db, ctx, "plan_subscribed")
    assert len(events) == 1
    assert events[0].properties == {
        "organization_id": str(ctx.org_id),
        "plan": "pro",
        "interval": "monthly",
    }
    assert (await audits(db, ctx, actions.PLAN_SUBSCRIBED))[0].meta == {
        "plan": "pro",
        "interval": "monthly",
        "previous_plan": "free",
        "subscription_id": "sub_plan",
    }


async def test_out_of_order_event_uses_stripe_state(client, db, webhook_context):
    ctx = webhook_context
    await post_plan(client, ctx, status="canceled")
    assert (await subscription(db, ctx.org_id)).status == PlanSubscriptionStatus.ACTIVE
    ctx.snapshot = replace(ctx.snapshot, status=PlanSubscriptionStatus.CANCELED)
    await post_plan(client, ctx, status="active")
    assert (await subscription(db, ctx.org_id)).status == PlanSubscriptionStatus.CANCELED


async def test_subscription_deleted_falls_back_to_free(client, db, webhook_context):
    ctx = webhook_context
    await post_plan(client, ctx)
    ctx.snapshot = replace(ctx.snapshot, status=PlanSubscriptionStatus.CANCELED)
    await post_plan(client, ctx, "customer.subscription.deleted")
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.FREE
    assert len(await audits(db, ctx, actions.PLAN_CANCELED)) == 1
    assert len(await activity(db, ctx, "plan_canceled")) == 1


async def test_past_due_keeps_plan_within_grace_then_free(client, db, webhook_context):
    ctx = webhook_context
    now = datetime.now(UTC)
    ctx.snapshot = replace(
        ctx.snapshot,
        status=PlanSubscriptionStatus.PAST_DUE,
        current_period_end=now - timedelta(days=BILLING_PLAN_GRACE_DAYS) + timedelta(hours=1),
    )
    await post_plan(client, ctx)
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.PRO
    ctx.snapshot = replace(
        ctx.snapshot,
        current_period_end=now
        - timedelta(
            days=BILLING_PLAN_GRACE_DAYS,
            hours=1,
        ),
    )
    await post_plan(client, ctx)
    await subscription(db, ctx.org_id)
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.FREE


async def test_cancel_at_period_end_keeps_plan_until_end(client, db, webhook_context):
    ctx = webhook_context
    ctx.snapshot = replace(ctx.snapshot, cancel_at_period_end=True)
    await post_plan(client, ctx)
    row = await subscription(db, ctx.org_id)
    assert row.cancel_at_period_end
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.PRO
    ctx.snapshot = replace(
        ctx.snapshot,
        status=PlanSubscriptionStatus.CANCELED,
        current_period_end=datetime.now(UTC) - timedelta(seconds=1),
    )
    await post_plan(client, ctx, "customer.subscription.deleted")
    await subscription(db, ctx.org_id)
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.FREE


@pytest.mark.parametrize(
    "status", [PlanSubscriptionStatus.CANCELED, PlanSubscriptionStatus.INCOMPLETE]
)
async def test_stale_event_for_old_subscription_does_not_clobber_live_one(
    client,
    db,
    webhook_context,
    status,
):
    ctx = webhook_context
    await seed_subscription(db, ctx.org_id, stripe_subscription_id="sub_current", plan=Plan.TEAM)
    ctx.snapshot = replace(ctx.snapshot, subscription_id="sub_old", status=status)
    await post_plan(client, ctx)
    row = await subscription(db, ctx.org_id)
    assert row.stripe_subscription_id == "sub_current"
    assert row.plan == Plan.TEAM
    assert row.status == PlanSubscriptionStatus.ACTIVE
    assert await audits(db, ctx, actions.PLAN_CANCELED) == []


async def test_new_live_subscription_replaces_canceled_one(client, db, webhook_context):
    ctx = webhook_context
    old = await seed_subscription(
        db, ctx.org_id, stripe_subscription_id="sub_old", status=PlanSubscriptionStatus.CANCELED
    )
    old_id = old.id
    await post_plan(client, ctx)
    row = await subscription(db, ctx.org_id)
    assert row.id == old_id
    assert row.stripe_subscription_id == "sub_plan"
    assert row.status == PlanSubscriptionStatus.ACTIVE
    assert len(await audits(db, ctx, actions.PLAN_SUBSCRIBED)) == 1


async def test_community_event_does_not_touch_org_subscription(client, db, webhook_context):
    ctx = webhook_context
    await seed_subscription(db, ctx.org_id)
    db.add(CommunityMembership(user_id=ctx.user_id))
    await db.commit()
    await post_plan(
        client,
        ctx,
        id="sub_community",
        metadata={
            "community_membership": "1",
            "user_id": str(ctx.user_id),
        },
    )
    row = await subscription(db, ctx.org_id)
    assert row.stripe_subscription_id == "sub_plan"
    assert row.status == PlanSubscriptionStatus.ACTIVE
    member = await db.scalar(
        select(CommunityMembership).where(
            CommunityMembership.user_id == ctx.user_id,
        )
    )
    assert member.tier == MembershipTier.PREMIUM
    assert ctx.fetches == []


async def test_org_plan_event_does_not_touch_community_membership(client, db, webhook_context):
    ctx = webhook_context
    db.add(
        CommunityMembership(
            user_id=ctx.user_id,
            tier=MembershipTier.PREMIUM,
            subscription_status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_community",
        )
    )
    await db.commit()
    await post_plan(client, ctx)
    ctx.snapshot = replace(ctx.snapshot, status=PlanSubscriptionStatus.CANCELED)
    await post_plan(client, ctx, "customer.subscription.deleted")
    member = await db.scalar(
        select(CommunityMembership).where(
            CommunityMembership.user_id == ctx.user_id,
        )
    )
    assert member.tier == MembershipTier.PREMIUM
    assert member.stripe_subscription_id == "sub_community"
    assert (await subscription(db, ctx.org_id)).status == PlanSubscriptionStatus.CANCELED


async def test_untagged_subscription_event_is_ignored(client, db, webhook_context):
    for etype in (
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        await post_plan(client, webhook_context, etype, metadata={})
    assert await subscription(db, webhook_context.org_id) is None
    assert webhook_context.fetches == []


@pytest.mark.parametrize("org_id", [None, "malformed", uuid.uuid4()])
async def test_unknown_org_is_ignored_without_error(client, db, webhook_context, org_id):
    ctx = webhook_context
    ctx.snapshot = replace(ctx.snapshot, org_id=org_id)
    await post_plan(client, ctx, metadata={"org_plan": "1"})
    assert await subscription(db, ctx.org_id) is None
    assert await audits(db, ctx, actions.PLAN_SUBSCRIBED) == []


async def test_unrecognized_price_keeps_existing_plan(client, db, webhook_context):
    ctx = webhook_context
    await seed_subscription(db, ctx.org_id, plan=Plan.TEAM, interval=BillingInterval.ANNUAL)
    ctx.snapshot = replace(
        ctx.snapshot,
        plan=None,
        interval=None,
        status=PlanSubscriptionStatus.PAST_DUE,
        cancel_at_period_end=True,
    )
    await post_plan(client, ctx)
    row = await subscription(db, ctx.org_id)
    assert (row.plan, row.interval) == (Plan.TEAM, BillingInterval.ANNUAL)
    assert row.status == PlanSubscriptionStatus.PAST_DUE
    assert row.current_period_end == ctx.snapshot.current_period_end
    assert row.cancel_at_period_end
    assert await activity(db, ctx, "plan_changed") == []


async def test_plan_change_emits_plan_changed_once(client, db, webhook_context):
    ctx = webhook_context
    await post_plan(client, ctx)
    ctx.snapshot = replace(ctx.snapshot, plan=Plan.TEAM, interval=BillingInterval.ANNUAL)
    await post_plan(client, ctx)
    await post_plan(client, ctx)
    assert (await subscription(db, ctx.org_id)).plan == Plan.TEAM
    assert len(await audits(db, ctx, actions.PLAN_CHANGED)) == 1
    events = await activity(db, ctx, "plan_changed")
    assert len(events) == 1
    assert (await audits(db, ctx, actions.PLAN_CHANGED))[0].meta["previous_plan"] == "pro"
    assert events[0].properties["plan"] == "team"


async def test_concurrent_first_events_create_one_subscription(client, db, webhook_context):
    ctx = webhook_context
    await asyncio.gather(post_plan(client, ctx), post_plan(client, ctx))
    assert len((await db.scalars(select(Subscription))).all()) == 1
    assert len(await audits(db, ctx, actions.PLAN_SUBSCRIBED)) == 1
    assert len(await activity(db, ctx, "plan_subscribed")) == 1


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("trialing", "trialing"),
        ("active", "active"),
        ("past_due", "past_due"),
        ("incomplete", "incomplete"),
        ("canceled", "canceled"),
        ("unpaid", "canceled"),
        ("incomplete_expired", "canceled"),
        ("paused", "canceled"),
        ("unknown", "canceled"),
    ],
)
async def test_gateway_snapshot_maps_status_and_metadata(monkeypatch, raw, expected):
    org_id = uuid.uuid4()
    monkeypatch.setattr(settings, "stripe_price_plan_team_annual", "price_team_year")
    monkeypatch.setattr(
        stripe.Subscription,
        "retrieve",
        lambda _: {
            "id": "sub_fetch",
            "status": raw,
            "cancel_at_period_end": True,
            "metadata": {"org_plan": "1", "organization_id": str(org_id), "user_id": "broken"},
            "items": {
                "data": [{"price": {"id": "price_team_year"}, "current_period_end": 1893456000}]
            },
        },
    )
    snapshot = await StripeGateway().fetch_subscription("sub_fetch")
    assert snapshot.status.value == expected
    assert snapshot.org_id == org_id
    assert snapshot.user_id is None
    assert snapshot.plan == Plan.TEAM
    assert snapshot.interval == BillingInterval.ANNUAL
    assert snapshot.current_period_end == datetime(2030, 1, 1, tzinfo=UTC)
    assert snapshot.cancel_at_period_end
    assert snapshot.is_org_plan


async def test_missing_or_untagged_fetch_is_ignored(client, db, webhook_context):
    ctx = webhook_context
    ctx.snapshot = replace(ctx.snapshot, is_org_plan=False)
    await post_plan(client, ctx)
    ctx.snapshot = None
    await post_plan(client, ctx)
    assert await subscription(db, ctx.org_id) is None


async def test_no_actor_still_audits(client, db, webhook_context):
    ctx = webhook_context
    ctx.snapshot = replace(ctx.snapshot, user_id=None)
    await post_plan(client, ctx)
    assert len(await audits(db, ctx, actions.PLAN_SUBSCRIBED)) == 1
    assert await activity(db, ctx, "plan_subscribed") == []


async def test_gateway_missing_subscription_returns_none(monkeypatch):
    def missing(_):
        raise stripe.InvalidRequestError(
            "No such subscription",
            "id",
            code="resource_missing",
            http_status=404,
        )

    monkeypatch.setattr(stripe.Subscription, "retrieve", missing)
    assert await StripeGateway().fetch_subscription("sub_missing") is None


async def test_metadata_org_falls_back_to_event(client, db, webhook_context):
    ctx = webhook_context
    ctx.snapshot = replace(ctx.snapshot, org_id=None)
    await post_plan(client, ctx)
    assert (await subscription(db, ctx.org_id)).plan == Plan.PRO


async def test_snapshot_is_refetched_after_lock(client, db, webhook_context, monkeypatch):
    ctx = webhook_context
    await seed_subscription(db, ctx.org_id)
    calls = []

    async def fetch(self, subscription_id):
        calls.append(subscription_id)
        if len(calls) == 1:
            return replace(ctx.snapshot, status=PlanSubscriptionStatus.CANCELED)
        return ctx.snapshot

    monkeypatch.setattr(StripeGateway, "fetch_subscription", fetch)
    await post_plan(client, ctx)
    assert len(calls) == 2
    assert (await subscription(db, ctx.org_id)).status == PlanSubscriptionStatus.ACTIVE
    assert await audits(db, ctx, actions.PLAN_CANCELED) == []


@pytest.mark.parametrize(
    "status, plan",
    [
        (PlanSubscriptionStatus.CANCELED, Plan.PRO),
        (PlanSubscriptionStatus.INCOMPLETE, Plan.PRO),
        (PlanSubscriptionStatus.ACTIVE, None),
    ],
)
async def test_unusable_snapshot_does_not_create_subscription(
    client,
    db,
    webhook_context,
    status,
    plan,
):
    ctx = webhook_context
    ctx.snapshot = replace(ctx.snapshot, status=status, plan=plan)
    await post_plan(client, ctx)
    assert await subscription(db, ctx.org_id) is None


async def test_cancel_after_grace_lapse_still_emits_plan_canceled(client, db, webhook_context):
    ctx = webhook_context
    period_end = datetime.now(UTC) - timedelta(days=BILLING_PLAN_GRACE_DAYS + 21)
    await seed_subscription(
        db,
        ctx.org_id,
        status=PlanSubscriptionStatus.PAST_DUE,
        current_period_end=period_end,
    )
    assert await build_plan_reader(db).plan_for(ctx.org_id) == Plan.FREE
    ctx.snapshot = replace(
        ctx.snapshot, status=PlanSubscriptionStatus.CANCELED, current_period_end=period_end
    )
    await post_plan(client, ctx, "customer.subscription.deleted")
    await post_plan(client, ctx, "customer.subscription.deleted")
    entries = await audits(db, ctx, actions.PLAN_CANCELED)
    assert len(entries) == 1
    assert entries[0].meta == {
        "plan": "free",
        "interval": "monthly",
        "previous_plan": "pro",
        "subscription_id": "sub_plan",
    }
    events = await activity(db, ctx, "plan_canceled")
    assert len(events) == 1
    assert events[0].properties == {"organization_id": str(ctx.org_id), "plan": "pro"}


async def test_interval_change_emits_plan_changed(client, db, webhook_context):
    ctx = webhook_context
    await seed_subscription(db, ctx.org_id)
    ctx.snapshot = replace(ctx.snapshot, interval=BillingInterval.ANNUAL)
    await post_plan(client, ctx)
    await post_plan(client, ctx)
    row = await subscription(db, ctx.org_id)
    assert (row.plan, row.interval) == (Plan.PRO, BillingInterval.ANNUAL)
    entries = await audits(db, ctx, actions.PLAN_CHANGED)
    assert len(entries) == 1
    assert entries[0].meta == {
        "plan": "pro",
        "interval": "annual",
        "previous_plan": "pro",
        "subscription_id": "sub_plan",
    }
    events = await activity(db, ctx, "plan_changed")
    assert len(events) == 1
    assert events[0].properties == {
        "organization_id": str(ctx.org_id),
        "plan": "pro",
        "interval": "annual",
    }
    assert (
        await db.scalar(
            select(CreditTransaction).where(
                CreditTransaction.organization_id == ctx.org_id,
            )
        )
        is None
    )


@pytest.mark.parametrize("grace_lapsed", [False, True])
async def test_past_due_then_recovered_emits_no_lifecycle_event(
    client,
    db,
    webhook_context,
    grace_lapsed,
):
    ctx = webhook_context
    await seed_subscription(db, ctx.org_id)
    db.add(
        CreditWallet(
            organization_id=ctx.org_id,
            balance=MONTHLY_ALLOWANCE_CREDITS,
            allowance_period=datetime.now(UTC).strftime("%Y-%m"),
        )
    )
    await db.commit()
    active_snapshot = ctx.snapshot
    past_due_snapshot = replace(
        ctx.snapshot,
        status=PlanSubscriptionStatus.PAST_DUE,
        current_period_end=(
            datetime.now(UTC) - timedelta(days=BILLING_PLAN_GRACE_DAYS + 1)
            if grace_lapsed
            else datetime.now(UTC)
        ),
    )
    # Repeat recovery to cover the same-month top-up key as well as redelivery.
    for _ in range(2):
        ctx.snapshot = past_due_snapshot
        await post_plan(client, ctx)
        ctx.snapshot = active_snapshot
        await post_plan(client, ctx)
        await post_plan(client, ctx)
    for action in (actions.PLAN_SUBSCRIBED, actions.PLAN_CHANGED, actions.PLAN_CANCELED):
        assert await audits(db, ctx, action) == []
    for event in ("plan_subscribed", "plan_changed", "plan_canceled"):
        assert await activity(db, ctx, event) == []
    wallet = await db.scalar(
        select(CreditWallet).where(
            CreditWallet.organization_id == ctx.org_id,
        )
    )
    assert wallet.balance == (
        PLANS[Plan.PRO].monthly_credits if grace_lapsed else MONTHLY_ALLOWANCE_CREDITS
    )
    entries = list(
        (
            await db.scalars(
                select(CreditTransaction).where(
                    CreditTransaction.organization_id == ctx.org_id,
                )
            )
        ).all()
    )
    assert len(entries) == (1 if grace_lapsed else 0)
    if grace_lapsed:
        assert entries[0].amount == PLANS[Plan.PRO].monthly_credits - MONTHLY_ALLOWANCE_CREDITS


async def test_analytics_properties_match_event_registry(client, db, webhook_context):
    # The generated Python registry exposes names only; params live in its TOML source.
    registry = tomllib.loads(
        (Path(__file__).resolve().parents[2] / "shared/events.toml").read_text()
    )["server"]
    ctx = webhook_context
    await post_plan(client, ctx)
    ctx.snapshot = replace(ctx.snapshot, plan=Plan.TEAM, interval=BillingInterval.ANNUAL)
    await post_plan(client, ctx)
    ctx.snapshot = replace(ctx.snapshot, status=PlanSubscriptionStatus.CANCELED)
    await post_plan(client, ctx, "customer.subscription.deleted")
    for name, plan in (
        ("plan_subscribed", "pro"),
        ("plan_changed", "team"),
        ("plan_canceled", "team"),
    ):
        events = await activity(db, ctx, name)
        assert len(events) == 1
        properties = events[0].properties
        assert set(properties) == set(registry[name]["params"])
        assert properties["organization_id"] == str(ctx.org_id)
        assert properties["plan"] == plan
