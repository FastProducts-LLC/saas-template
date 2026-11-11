"""Public catalog, tenant permissions, and real gateway checkout parameters."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
import stripe
from sqlalchemy import select

import app.domains.billing.application.plans as plan_cases
from app.core.config import settings
from app.domains.billing.domain import BillingAccount
from app.domains.billing.domain.entities import Subscription
from app.domains.billing.domain.value_objects import (
    PAID_PLANS,
    PLANS,
    BillingInterval,
    Plan,
    PlanSubscriptionStatus,
)
from app.domains.credits.domain import MONTHLY_ALLOWANCE_CREDITS
from tests.helpers import create_org, register_and_login
from tests.test_billing import add_member


@pytest_asyncio.fixture
async def plan_context(client, monkeypatch):
    user, headers = await register_and_login(client)
    org = await create_org(client, headers)
    calls, customers = [], []
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    for plan in PAID_PLANS:
        for interval in BillingInterval:
            monkeypatch.setattr(
                settings,
                f"stripe_price_plan_{plan.value}_{interval.value}",
                f"price_{plan.value}_{interval.value}",
            )

    def checkout(**kwargs):
        calls.append(kwargs)
        return {"url": "https://checkout.stripe.test/plan"}

    def customer(**kwargs):
        customers.append(kwargs)
        return {"id": "cus_org_plan"}

    monkeypatch.setattr(stripe.checkout.Session, "create", checkout)
    monkeypatch.setattr(stripe.Customer, "create", customer)
    return SimpleNamespace(
        user=user,
        headers=headers,
        org_id=uuid.UUID(org["id"]),
        path=f"/api/orgs/{org['id']}/billing",
        calls=calls,
        customers=customers,
    )


async def seed_subscription(db, org_id, **overrides):
    values = dict(
        organization_id=org_id,
        stripe_subscription_id="sub_plan",
        plan=Plan.PRO,
        interval=BillingInterval.MONTHLY,
        status=PlanSubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(UTC) + timedelta(days=30),
    )
    values.update(overrides)
    subscription = Subscription(**values)
    db.add(subscription)
    await db.commit()
    return subscription


async def checkout(client, ctx, **overrides):
    payload = {"plan": "pro", "interval": "monthly", **overrides}
    return await client.post(ctx.path + "/plan/checkout", headers=ctx.headers, json=payload)


async def test_list_plans_public(client, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    for plan in PAID_PLANS:
        for interval in BillingInterval:
            monkeypatch.setattr(settings, f"stripe_price_plan_{plan.value}_{interval.value}", "")
    monkeypatch.setattr(settings, "stripe_price_plan_pro_monthly", "price_pro_monthly")
    response = await client.get("/api/billing/plans")
    assert response.status_code == 200
    assert response.json() == [
        {
            "plan": spec.plan.value,
            "name": spec.name,
            "monthly_price_cents": spec.monthly_price_cents,
            "annual_price_cents": spec.annual_price_cents,
            "monthly_credits": (
                MONTHLY_ALLOWANCE_CREDITS if spec.monthly_credits is None else spec.monthly_credits
            ),
            "purchasable": {"monthly": spec.plan == Plan.PRO, "annual": False},
        }
        for spec in PLANS.values()
    ]
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    assert all(
        not any(p["purchasable"].values()) for p in (await client.get("/api/billing/plans")).json()
    )


async def test_billing_plan_defaults_to_free(client, db, plan_context):
    ctx = plan_context
    response = await client.get(ctx.path + "/plan", headers=ctx.headers)
    assert response.status_code == 200
    assert response.json() == {"plan": "free", "subscription": None}
    assert (
        await db.scalar(
            select(BillingAccount).where(
                BillingAccount.organization_id == ctx.org_id,
            )
        )
        is None
    )
    assert ctx.customers == []


async def test_billing_plan_reports_active_subscription(client, db, plan_context):
    ctx = plan_context
    row = await seed_subscription(db, ctx.org_id)
    response = await client.get(ctx.path + "/plan", headers=ctx.headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "pro"
    assert data["subscription"] == {
        "plan": "pro",
        "interval": "monthly",
        "status": "active",
        "current_period_end": row.current_period_end.isoformat().replace("+00:00", "Z"),
        "cancel_at_period_end": False,
    }


async def test_billing_plan_requires_membership(client, plan_context):
    _, headers = await register_and_login(client, "outsider@example.com")
    response = await client.get(plan_context.path + "/plan", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "ERR_PERM_002"


async def test_billing_overview_response_is_unchanged(client, db, plan_context):
    ctx = plan_context
    await seed_subscription(db, ctx.org_id)
    assert (await client.get(ctx.path, headers=ctx.headers)).json() == {
        "has_billing_account": False,
    }
    # Checkout on another org exercises the existing customer-backed overview too.
    org = await create_org(client, ctx.headers, "Second")
    path = f"/api/orgs/{org['id']}/billing"
    response = await client.post(
        path + "/plan/checkout", headers=ctx.headers, json={"plan": "pro", "interval": "monthly"}
    )
    assert response.status_code == 200
    assert (await client.get(path, headers=ctx.headers)).json() == {"has_billing_account": True}


async def test_plan_checkout_returns_url_and_tags_metadata(client, db, plan_context):
    ctx = plan_context
    response = await checkout(client, ctx)
    assert response.status_code == 200, response.text
    assert response.json() == {"url": "https://checkout.stripe.test/plan"}
    call = ctx.calls[0]
    expected = {
        "org_plan": "1",
        "organization_id": str(ctx.org_id),
        "plan": "pro",
        "interval": "monthly",
        "user_id": ctx.user["id"],
    }
    assert call["mode"] == "subscription"
    assert call["metadata"] == expected
    assert call["subscription_data"]["metadata"] == expected
    assert "trial_period_days" not in call["subscription_data"]
    assert call["client_reference_id"] == str(ctx.org_id)
    assert call["line_items"] == [{"price": "price_pro_monthly", "quantity": 1}]
    assert call["success_url"] == f"{settings.frontend_url}/billing?status=success"
    assert call["cancel_url"] == f"{settings.frontend_url}/billing?status=canceled"
    account = await db.scalar(
        select(BillingAccount).where(
            BillingAccount.organization_id == ctx.org_id,
        )
    )
    assert account.stripe_customer_id == call["customer"]
    assert (await checkout(client, ctx)).status_code == 200
    assert len(ctx.customers) == 1


async def test_plan_checkout_rejects_free_plan(client, plan_context, monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    response = await checkout(client, plan_context, plan="free")
    assert response.status_code == 422
    assert plan_context.calls == plan_context.customers == []


@pytest.mark.parametrize("missing", ["stripe_secret_key", "stripe_price_plan_pro_monthly"])
async def test_plan_checkout_unconfigured_price_conflicts(
    client, db, plan_context, monkeypatch, missing
):
    await seed_subscription(db, plan_context.org_id)
    monkeypatch.setattr(settings, missing, "")
    response = await checkout(client, plan_context)
    assert response.status_code == 409
    assert response.json()["code"] == "ERR_BILL_008"
    assert plan_context.customers == []


@pytest.mark.parametrize(
    "status",
    [
        PlanSubscriptionStatus.ACTIVE,
        PlanSubscriptionStatus.TRIALING,
        PlanSubscriptionStatus.PAST_DUE,
    ],
)
async def test_plan_checkout_when_already_subscribed_conflicts(client, db, plan_context, status):
    await seed_subscription(db, plan_context.org_id, status=status)
    response = await checkout(client, plan_context)
    assert response.status_code == 409
    assert response.json()["code"] == "ERR_BILL_009"
    assert plan_context.customers == []


async def test_plan_checkout_forbidden_for_plain_member(client, db, plan_context):
    user, headers = await register_and_login(client, "member@example.com")
    await add_member(db, str(plan_context.org_id), user["id"])
    response = await client.post(
        plan_context.path + "/plan/checkout",
        headers=headers,
        json={"plan": "pro", "interval": "monthly"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ERR_PERM_001"
    assert plan_context.customers == []


async def test_plan_checkout_passes_trial_days_when_configured(client, plan_context, monkeypatch):
    monkeypatch.setattr(plan_cases, "BILLING_TRIAL_DAYS", 14)
    response = await checkout(client, plan_context, plan="team", interval="annual")
    assert response.status_code == 200
    assert plan_context.calls[0]["subscription_data"]["trial_period_days"] == 14
    assert plan_context.calls[0]["line_items"] == [{"price": "price_team_annual", "quantity": 1}]


async def test_plan_checkout_other_org_is_forbidden(client, plan_context):
    _, headers = await register_and_login(client, "other@example.com")
    await create_org(client, headers, "Other")
    response = await client.post(
        plan_context.path + "/plan/checkout",
        headers=headers,
        json={"plan": "pro", "interval": "monthly"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "ERR_PERM_002"
    assert plan_context.customers == []


async def test_stripe_sync_org_products_and_recurring_prices(monkeypatch):
    from scripts import stripe_sync

    products, prices = [], {}

    def create_product(**kwargs):
        product = {"id": f"prod_{len(products)}", **kwargs}
        products.append(product)
        return product

    def create_price(**kwargs):
        price = {"id": f"price_{len(prices)}", "type": "recurring", **kwargs}
        prices[kwargs["lookup_key"]] = price
        return price

    monkeypatch.setattr(
        stripe.Product,
        "list",
        lambda **kw: SimpleNamespace(
            auto_paging_iter=lambda: iter(products),
        ),
    )
    monkeypatch.setattr(stripe.Product, "create", create_product)
    monkeypatch.setattr(
        stripe.Price,
        "list",
        lambda **kw: SimpleNamespace(
            data=[prices[key] for key in kw["lookup_keys"] if key in prices],
        ),
    )
    monkeypatch.setattr(stripe.Price, "create", create_price)
    env_lines = stripe_sync.sync_plans()
    assert len(products) == len(PAID_PLANS)
    assert len(prices) == len(PAID_PLANS) * len(BillingInterval)
    for plan in PAID_PLANS:
        product = next(p for p in products if p["metadata"] == {"org_plan": plan.value})
        for interval in BillingInterval:
            price = prices[f"plan_{plan.value}_{interval.value}"]
            assert price["product"] == product["id"]
            assert price["unit_amount"] == PLANS[plan].price_cents(interval)
            assert price["recurring"] == {
                "interval": "month" if interval == BillingInterval.MONTHLY else "year",
            }
            assert (
                f"STRIPE_PRICE_PLAN_{plan.value.upper()}_{interval.value.upper()}={price['id']}"
                in env_lines
            )
    assert stripe_sync.sync_plans() == env_lines
    assert len(products) == len(PAID_PLANS)
    assert len(prices) == len(PAID_PLANS) * len(BillingInterval)


async def test_stripe_sync_org_price_drift(monkeypatch):
    from scripts import stripe_sync

    for plan in PAID_PLANS:
        for interval in BillingInterval:
            monkeypatch.setattr(settings, f"stripe_price_plan_{plan.value}_{interval.value}", "")
    monkeypatch.setattr(settings, "stripe_price_plan_pro_annual", "price_pro_year")
    price = {
        "id": "price_pro_year",
        "unit_amount": PLANS[Plan.PRO].annual_price_cents,
        "currency": "usd",
        "type": "recurring",
        "recurring": {"interval": "year"},
    }
    # Real SDK objects must work too, not just dict-shaped test doubles.
    monkeypatch.setattr(stripe.Price, "retrieve", lambda _: stripe.Price.construct_from(price, ""))
    assert stripe_sync.check_plans() == []
    price.update(unit_amount=1, currency="eur", recurring={"interval": "month"})
    problems = stripe_sync.check_plans()
    assert len(problems) == 3
    assert any("amount:" in problem for problem in problems)
    assert any("currency:" in problem for problem in problems)
    assert any("interval:" in problem for problem in problems)
