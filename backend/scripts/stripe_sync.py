"""Reconcile credit packs, community memberships, and organization plans with Stripe.

    docker compose exec backend python scripts/stripe_sync.py          # create/update
    docker compose exec backend python scripts/stripe_sync.py --check  # verify only (CI/cron)

The displayed price comes from CREDIT_PACKS (credits domain); the *charged*
price lives on the Stripe Price object. Nothing else links the two, so a
catalog edit without a Stripe update silently advertises one price and
charges another. This script closes that gap:

  sync mode   — for each pack, find the Price by lookup key `credits_<pack>`
                (creating the Product + Price if missing). If the amount has
                drifted, a replacement Price is created and the lookup key is
                transferred (Stripe prices are immutable). Ends by printing the
                STRIPE_PRICE_CREDITS_* env lines to paste into your env file.
  --check     — verify each configured STRIPE_PRICE_CREDITS_* id exists and
                its amount/currency match the catalog. No writes.

Community memberships and organization plans follow the same reconciliation.
Org plans use one Product (metadata org_plan=<plan>) and monthly/annual recurring
Prices with lookup keys plan_<plan>_<interval>. Sync prints STRIPE_PRICE_PLAN_*
env lines; --check verifies amount, currency, and recurrence against PLANS.

Needs STRIPE_SECRET_KEY. Test mode and live mode are separate Stripe worlds —
run once per environment.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.domains.community.domain.value_objects import (  # noqa: E402
    COMMUNITY_PLANS,
    CommunityPlan,
    CommunityPlanSpec,
)
from app.domains.credits.domain.value_objects import (  # noqa: E402
    CREDIT_PACKS,
    CreditPack,
    CreditPackSpec,
)

CURRENCY = "usd"


def _env_var(pack: CreditPack) -> str:
    return f"STRIPE_PRICE_CREDITS_{pack.value.upper()}"


def _configured_price_id(pack: CreditPack) -> str:
    return getattr(settings, f"stripe_price_credits_{pack.value}", "")


def _price_matches(price: stripe.Price, spec: CreditPackSpec) -> list[str]:
    problems = []
    if price["unit_amount"] != spec.price_cents:
        problems.append(
            f"amount: Stripe charges {price['unit_amount']}¢, catalog displays {spec.price_cents}¢"
        )
    if price["currency"] != CURRENCY:
        problems.append(f"currency: Stripe {price['currency']!r}, expected {CURRENCY!r}")
    if price["type"] != "one_time":
        problems.append(f"type: Stripe {price['type']!r}, packs are one_time payments")
    return problems


def check() -> None:
    """Verify configured price ids against the catalog. Read-only."""
    failures: list[str] = []
    for pack, spec in CREDIT_PACKS.items():
        price_id = _configured_price_id(pack)
        if not price_id:
            print(f"  {pack.value}: no {_env_var(pack)} set — pack is disabled (not purchasable)")
            continue
        try:
            price = stripe.Price.retrieve(price_id)
        except stripe.InvalidRequestError as exc:
            reason = exc.user_message or exc
            failures.append(f"{pack.value}: {_env_var(pack)}={price_id} — {reason}")
            continue
        if problems := _price_matches(price, spec):
            failures.extend(f"{pack.value} ({price_id}): {p}" for p in problems)
        else:
            print(f"  {pack.value}: {price_id} OK ({spec.price_cents}¢ / {spec.credits} credits)")
    failures.extend(check_community())
    failures.extend(check_plans())
    if failures:
        print("\nDRIFT between the local catalogs and Stripe:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(
            "Fix: edit CREDIT_PACKS / COMMUNITY_PLANS / PLANS or run "
            "`python scripts/stripe_sync.py` to issue replacement Stripe prices, "
            "then update the env vars it prints."
        )
    print("credit packs, community plans, organization plans, and Stripe are in sync")


def _community_env_var(plan: CommunityPlan) -> str:
    return f"STRIPE_PRICE_COMMUNITY_{plan.value.upper()}"


def _community_configured_price_id(plan: CommunityPlan) -> str:
    return getattr(settings, f"stripe_price_community_{plan.value}", "")


def _community_price_matches(price: stripe.Price, spec: CommunityPlanSpec) -> list[str]:
    problems = []
    if price["unit_amount"] != spec.price_cents:
        problems.append(
            f"amount: Stripe charges {price['unit_amount']}¢, catalog displays {spec.price_cents}¢"
        )
    if price["currency"] != CURRENCY:
        problems.append(f"currency: Stripe {price['currency']!r}, expected {CURRENCY!r}")
    if price["type"] != "recurring":
        problems.append(f"type: Stripe {price['type']!r}, membership plans are recurring")
    elif (price.get("recurring") or {}).get("interval") != spec.interval:
        problems.append(
            f"interval: Stripe {(price.get('recurring') or {}).get('interval')!r}, "
            f"expected {spec.interval!r}"
        )
    return problems


def check_community() -> list[str]:
    """Verify configured community plan price ids. Read-only; returns failures."""
    failures: list[str] = []
    for plan, spec in COMMUNITY_PLANS.items():
        price_id = _community_configured_price_id(plan)
        if not price_id:
            print(
                f"  community/{plan.value}: no {_community_env_var(plan)} set — "
                "plan is disabled (not purchasable)"
            )
            continue
        try:
            price = stripe.Price.retrieve(price_id)
        except stripe.InvalidRequestError as exc:
            reason = exc.user_message or exc
            failures.append(
                f"community/{plan.value}: {_community_env_var(plan)}={price_id} — {reason}"
            )
            continue
        if problems := _community_price_matches(price, spec):
            failures.extend(f"community/{plan.value} ({price_id}): {p}" for p in problems)
        else:
            print(
                f"  community/{plan.value}: {price_id} OK ({spec.price_cents}¢ / {spec.interval})"
            )
    return failures


def _find_community_product(plan: CommunityPlan) -> stripe.Product | None:
    for product in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if product.get("metadata", {}).get("community_plan") == plan.value:
            return product
    return None


def _lookup_community_price(plan: CommunityPlan) -> stripe.Price | None:
    prices = stripe.Price.list(lookup_keys=[f"community_{plan.value}"], active=True, limit=1)
    return prices.data[0] if prices.data else None


def sync_community() -> list[str]:
    """Ensure a Product + correctly-priced recurring Price per plan."""
    env_lines: list[str] = []
    for plan, spec in COMMUNITY_PLANS.items():
        lookup_key = f"community_{plan.value}"
        price = _lookup_community_price(plan)

        if price is not None and not _community_price_matches(price, spec):
            print(f"  community/{plan.value}: {price['id']} already correct")
            env_lines.append(f"{_community_env_var(plan)}={price['id']}")
            continue

        product = _find_community_product(plan)
        if product is None:
            product = stripe.Product.create(
                name=f"Community membership — {spec.name}",
                metadata={"community_plan": plan.value},
            )
            print(f"  community/{plan.value}: created product {product['id']}")

        if price is not None:
            print(f"  community/{plan.value}: {price['id']} drifted — issuing replacement")
        new_price = stripe.Price.create(
            product=product["id"],
            unit_amount=spec.price_cents,
            currency=CURRENCY,
            recurring={"interval": spec.interval},
            lookup_key=lookup_key,
            transfer_lookup_key=True,
            metadata={"community_plan": plan.value},
        )
        print(
            f"  community/{plan.value}: price {new_price['id']} "
            f"({spec.price_cents}¢/{spec.interval}, lookup {lookup_key})"
        )
        env_lines.append(f"{_community_env_var(plan)}={new_price['id']}")
    return env_lines


def _find_product(pack: CreditPack) -> stripe.Product | None:
    for product in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if product.get("metadata", {}).get("credit_pack") == pack.value:
            return product
    return None


def _lookup_price(pack: CreditPack) -> stripe.Price | None:
    prices = stripe.Price.list(lookup_keys=[f"credits_{pack.value}"], active=True, limit=1)
    return prices.data[0] if prices.data else None


def sync() -> None:
    """Ensure a Product + correctly-priced Price per pack; print env lines."""
    env_lines: list[str] = []
    for pack, spec in CREDIT_PACKS.items():
        lookup_key = f"credits_{pack.value}"
        price = _lookup_price(pack)

        if price is not None and not _price_matches(price, spec):
            print(f"  {pack.value}: {price['id']} already correct")
            env_lines.append(f"{_env_var(pack)}={price['id']}")
            continue

        product = _find_product(pack)
        if product is None:
            product = stripe.Product.create(
                name=f"{spec.name} credit pack ({spec.credits} credits)",
                metadata={"credit_pack": pack.value, "credits": str(spec.credits)},
            )
            print(f"  {pack.value}: created product {product['id']}")

        if price is not None:
            print(
                f"  {pack.value}: {price['id']} drifted "
                f"({price['unit_amount']}¢ != {spec.price_cents}¢) — issuing replacement"
            )
        new_price = stripe.Price.create(
            product=product["id"],
            unit_amount=spec.price_cents,
            currency=CURRENCY,
            lookup_key=lookup_key,
            transfer_lookup_key=True,
            metadata={"credit_pack": pack.value, "credits": str(spec.credits)},
        )
        print(f"  {pack.value}: price {new_price['id']} ({spec.price_cents}¢, lookup {lookup_key})")
        env_lines.append(f"{_env_var(pack)}={new_price['id']}")

    env_lines.extend(sync_community())
    env_lines.extend(sync_plans())

    print("\nSet these in your env file (env/<slug>.env in prod, .env in dev):")
    for line in env_lines:
        print(f"  {line}")


def _org_plan_prices():
    from app.domains.billing.domain.value_objects import PAID_PLANS, PLANS, BillingInterval

    for plan in PAID_PLANS:
        for interval in BillingInterval:
            yield PLANS[plan], interval


def _plan_env_var(plan, interval) -> str:
    return f"STRIPE_PRICE_PLAN_{plan.value.upper()}_{interval.value.upper()}"


def _plan_price_matches(price, spec, interval) -> list[str]:
    # Stripe >=15 objects expose recursive conversion, not dict.get().
    convert = getattr(price, "_to_dict_recursive", None)
    price = convert() if callable(convert) else price
    problems = []
    if price["unit_amount"] != spec.price_cents(interval):
        problems.append(
            f"amount: expected {spec.price_cents(interval)}¢, got {price['unit_amount']}¢"
        )
    if price["currency"] != CURRENCY:
        problems.append(f"currency: expected {CURRENCY}, got {price['currency']}")
    recurring = price.get("recurring") or {}
    expected = "month" if interval.value == "monthly" else "year"
    if price["type"] != "recurring":
        problems.append("type: organization plans must be recurring")
    if recurring.get("interval") != expected or recurring.get("interval_count", 1) != 1:
        problems.append(f"interval: expected one {expected}")
    return problems


def check_plans() -> list[str]:
    failures = []
    for spec, interval in _org_plan_prices():
        env = _plan_env_var(spec.plan, interval)
        price_id = getattr(settings, env.lower(), "")
        if not price_id:
            print(f"  {env}: unset — plan interval disabled")
            continue
        try:
            price = stripe.Price.retrieve(price_id)
        except stripe.InvalidRequestError as exc:
            failures.append(f"{env}={price_id}: {exc.user_message or exc}")
            continue
        problems = _plan_price_matches(price, spec, interval)
        failures.extend(f"{env}={price_id}: {problem}" for problem in problems)
        if not problems:
            print(f"  {env}={price_id} OK")
    return failures


def _find_plan_product(plan):
    for product in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        convert = getattr(product, "_to_dict_recursive", None)
        data = convert() if callable(convert) else product
        if (data.get("metadata") or {}).get("org_plan") == plan.value:
            return product
    return None


def sync_plans() -> list[str]:
    env_lines = []
    products = {}
    for spec, interval in _org_plan_prices():
        plan = spec.plan
        lookup_key = f"plan_{plan.value}_{interval.value}"
        prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
        price = prices.data[0] if prices.data else None
        if price is not None and not _plan_price_matches(price, spec, interval):
            env_lines.append(f"{_plan_env_var(plan, interval)}={price['id']}")
            print(f"  {lookup_key}: {price['id']} already correct")
            continue
        if plan not in products:
            products[plan] = _find_plan_product(plan) or stripe.Product.create(
                name=spec.name,
                metadata={"org_plan": plan.value},
            )
        new_price = stripe.Price.create(
            product=products[plan]["id"],
            unit_amount=spec.price_cents(interval),
            currency=CURRENCY,
            recurring={"interval": "month" if interval.value == "monthly" else "year"},
            lookup_key=lookup_key,
            transfer_lookup_key=True,
            metadata={"org_plan": plan.value},
        )
        print(f"  {lookup_key}: created price {new_price['id']}")
        env_lines.append(f"{_plan_env_var(plan, interval)}={new_price['id']}")
    return env_lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only; exit 1 on drift")
    args = parser.parse_args()

    if not settings.stripe_secret_key:
        sys.exit("STRIPE_SECRET_KEY is not set — nothing to reconcile against.")
    stripe.api_key = settings.stripe_secret_key

    mode = "live" if settings.stripe_secret_key.startswith("sk_live") else "test"
    print(
        f"Stripe {mode} mode · {len(CREDIT_PACKS)} packs + "
        f"{len(COMMUNITY_PLANS)} community plans + "
        f"{len({spec.plan for spec, _ in _org_plan_prices()})} organization plans in catalog"
    )
    if args.check:
        check()
    else:
        sync()


if __name__ == "__main__":
    main()
