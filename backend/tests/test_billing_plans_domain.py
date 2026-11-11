"""Organization plan prices and paid-access transitions."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domains.billing.domain import (
    PAID_PLANS,
    PLANS,
    BillingInterval,
    Plan,
    PlanSubscriptionStatus,
    Subscription,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def subscription(status: PlanSubscriptionStatus, **overrides) -> Subscription:
    values = {
        "organization_id": uuid.uuid4(),
        "stripe_subscription_id": "sub_plan",
        "plan": Plan.PRO,
        "interval": BillingInterval.MONTHLY,
        "status": status,
        "current_period_end": NOW,
    }
    return Subscription(**{**values, **overrides})


def test_plans_catalog_has_free_pro_team():
    assert set(PLANS) == {Plan.FREE, Plan.PRO, Plan.TEAM}
    assert PAID_PLANS == (Plan.PRO, Plan.TEAM)
    for plan, name, monthly, annual, credits in (
        (Plan.FREE, "Free", 0, 0, None),
        (Plan.PRO, "Pro", 2900, 29000, 200),
        (Plan.TEAM, "Team", 9900, 99000, 1000),
    ):
        spec = PLANS[plan]
        assert spec.plan == plan
        assert spec.name == name
        assert spec.price_cents(BillingInterval.MONTHLY) == monthly
        assert spec.price_cents(BillingInterval.ANNUAL) == annual
        assert spec.monthly_credits == credits


@pytest.mark.parametrize("plan", PAID_PLANS)
def test_effective_plan_active_returns_plan(plan):
    sub = subscription(PlanSubscriptionStatus.ACTIVE, plan=plan, cancel_at_period_end=True)
    assert sub.effective_plan(grace_days=3, now=NOW) == plan


@pytest.mark.parametrize("plan", PAID_PLANS)
def test_effective_plan_trialing_returns_plan(plan):
    assert (
        subscription(PlanSubscriptionStatus.TRIALING, plan=plan).effective_plan(
            grace_days=3, now=NOW
        )
        == plan
    )


@pytest.mark.parametrize("elapsed", [timedelta(days=2), timedelta(days=3)])
def test_effective_plan_past_due_within_grace_keeps_plan(elapsed):
    assert (
        subscription(PlanSubscriptionStatus.PAST_DUE).effective_plan(
            grace_days=3, now=NOW + elapsed
        )
        == Plan.PRO
    )


def test_effective_plan_past_due_after_grace_is_free():
    assert (
        subscription(PlanSubscriptionStatus.PAST_DUE).effective_plan(
            grace_days=3, now=NOW + timedelta(days=3, microseconds=1)
        )
        == Plan.FREE
    )


def test_effective_plan_past_due_without_period_end_is_free():
    assert (
        subscription(PlanSubscriptionStatus.PAST_DUE, current_period_end=None).effective_plan(
            grace_days=3, now=NOW
        )
        == Plan.FREE
    )


def test_effective_plan_canceled_is_free():
    assert (
        subscription(PlanSubscriptionStatus.CANCELED).effective_plan(grace_days=3, now=NOW)
        == Plan.FREE
    )


def test_effective_plan_incomplete_is_free():
    assert (
        subscription(PlanSubscriptionStatus.INCOMPLETE).effective_plan(grace_days=3, now=NOW)
        == Plan.FREE
    )


def test_subscription_apply_replaces_state_and_bumps_updated_at():
    sub = subscription(
        PlanSubscriptionStatus.INCOMPLETE, updated_at=datetime.now(UTC) - timedelta(days=1)
    )
    previous_updated_at = sub.updated_at
    sub.apply(
        stripe_subscription_id="sub_replacement",
        plan=Plan.TEAM,
        interval=BillingInterval.ANNUAL,
        status=PlanSubscriptionStatus.ACTIVE,
        current_period_end=NOW + timedelta(days=30),
        cancel_at_period_end=True,
    )
    assert sub.stripe_subscription_id == "sub_replacement"
    assert sub.plan == Plan.TEAM
    assert sub.interval == BillingInterval.ANNUAL
    assert sub.status == PlanSubscriptionStatus.ACTIVE
    assert sub.current_period_end == NOW + timedelta(days=30)
    assert sub.cancel_at_period_end
    assert sub.updated_at > previous_updated_at
    assert sub.updated_at.tzinfo == UTC
