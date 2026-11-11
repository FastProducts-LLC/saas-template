import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { formatMoney } from "../../../shared/lib/money";
import { Alert, Button, ErrorAlert, Spinner, Stamp } from "../../../shared/ui";
import { useMembershipCheckout, useMembershipPortal, useMyCommunity, usePlans } from "../api/hooks";
import type { Plan } from "../model/types";

function PlanCard({
  plan,
  onBuy,
  buying,
  highlight,
}: {
  plan: Plan;
  onBuy: () => void;
  buying: boolean;
  highlight: boolean;
}) {
  const perInterval = plan.interval === "year" ? "/year" : "/month";
  return (
    <div
      data-testid="community-plan-card"
      data-plan={plan.plan}
      className={`flex flex-col border bg-white p-5 ${
        highlight ? "border-[var(--teal-deep)]" : "border-[var(--line)]"
      }`}
      style={{ borderRadius: 4 }}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[var(--ink)]">{plan.name}</p>
        {highlight && (
          <Stamp className="border-[var(--teal-deep)] text-[var(--teal-deep)]">Best value</Stamp>
        )}
      </div>
      <p className="mt-3 font-[family-name:var(--font-display)] text-4xl font-bold tabular-nums text-[var(--ink)]">
        {formatMoney(plan.price_cents, { fractionDigits: 0 })}
        <span className="ml-1 font-[family-name:var(--font-body)] text-sm font-normal text-[var(--slate)]/70">
          {perInterval}
        </span>
      </p>
      <ul className="mt-4 flex-1 space-y-1.5 text-[13px] text-[var(--slate)]">
        <li>Direct messaging with any member</li>
        <li>Premium stamp on your profile</li>
        <li>Cancel anytime from the billing portal</li>
      </ul>
      <Button
        className="mt-5"
        onClick={onBuy}
        loading={buying}
        disabled={!plan.purchasable}
        data-testid={`community-buy-${plan.plan}`}
      >
        {plan.purchasable ? "Upgrade" : "Unavailable"}
      </Button>
    </div>
  );
}

export default function UpgradePage() {
  const [searchParams] = useSearchParams();
  const canceled = searchParams.get("status") === "canceled";
  const { data: me } = useMyCommunity();
  const { data: plans, isLoading } = usePlans();
  const checkout = useMembershipCheckout();
  const portal = useMembershipPortal();
  const [error, setError] = useState<unknown>(null);

  const membership = me?.membership;
  const isPremium = membership?.is_premium ?? false;

  return (
    <div className="gd-page-in mx-auto max-w-2xl" data-testid="community-upgrade-page">
      <Link
        to={ROUTES.community.list}
        className="text-sm font-medium text-[var(--teal-deep)] hover:underline"
      >
        ← Community
      </Link>
      <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--ink)]">
        Premium membership
      </h1>
      <p className="mt-2 text-sm text-[var(--slate)]">
        Unlock direct messaging and support the community.
      </p>

      {canceled && (
        <div className="mt-4">
          <Alert tone="warning" data-testid="community-checkout-canceled">
            Checkout canceled — you haven't been charged.
          </Alert>
        </div>
      )}
      <ErrorAlert error={error} className="mt-4" />

      {isPremium ? (
        <div
          className="mt-6 border border-[var(--line)] bg-white p-5"
          style={{ borderRadius: 4 }}
          data-testid="community-premium-active"
        >
          <div className="flex items-center gap-2">
            <Stamp className="border-[var(--success)] text-[var(--success)]">Active</Stamp>
            <p className="text-sm font-semibold text-[var(--ink)]">You're a premium member</p>
          </div>
          {membership?.current_period_end && (
            <p className="mt-2 font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)]/75">
              {membership.cancel_at_period_end ? "ends" : "renews"}{" "}
              {new Date(membership.current_period_end).toLocaleDateString()}
            </p>
          )}
          <Button
            variant="secondary"
            className="mt-4"
            onClick={() =>
              portal.mutate(undefined, {
                onError: (err: unknown) => setError(err),
              })
            }
            loading={portal.isPending}
            data-testid="community-manage-membership"
          >
            Manage membership
          </Button>
        </div>
      ) : isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {plans?.map((plan) => (
            <PlanCard
              key={plan.plan}
              plan={plan}
              highlight={plan.plan === "annual"}
              buying={checkout.isPending && checkout.variables === plan.plan}
              onBuy={() =>
                checkout.mutate(plan.plan, {
                  onError: (err: unknown) => setError(err),
                })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
