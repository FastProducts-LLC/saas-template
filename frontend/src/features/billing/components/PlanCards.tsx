import type { ReactNode } from "react";
import { PLAN_CONTENT } from "../../../shared/content/marketing";
import { formatMoney } from "../../../shared/lib/money";
import { Stamp } from "../../../shared/ui";
import { formatPlanPrice } from "../model/format";
import type { BillingInterval, Plan, PlanSpec } from "../model/types";

function Check() {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="mt-[3px] h-3.5 w-3.5 shrink-0 text-[var(--ink)]"
    >
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  );
}

export default function PlanCards({
  plans,
  interval,
  action,
  currentPlan,
}: {
  plans: PlanSpec[];
  interval: BillingInterval;
  action: (plan: PlanSpec) => ReactNode;
  /** Marks the organization's current plan. */
  currentPlan?: Plan;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {plans.map((plan) => {
        const saving = plan.monthly_price_cents * 12 - plan.annual_price_cents;
        const recommended = plan.plan === PLAN_CONTENT.recommended;
        const current = plan.plan === currentPlan;
        const price = interval === "monthly" ? plan.monthly_price_cents : plan.annual_price_cents;
        return (
          <article
            key={plan.plan}
            aria-label={`${plan.name} plan`}
            className={`flex flex-col rounded border bg-white p-6 ${
              recommended ? "border-[var(--ink)]" : "border-[var(--line)]"
            }`}
          >
            <div className="flex min-h-5 items-center gap-2">
              <h3 className="text-[15px] font-semibold text-[var(--ink)]">{plan.name}</h3>
              {current && <Stamp className="border-[var(--ink)] text-[var(--ink)]">Current</Stamp>}
              {recommended && !current && (
                <Stamp className="border-[var(--line)] text-[var(--slate)]">Recommended</Stamp>
              )}
            </div>
            <p className="mt-1 text-[13px] text-[var(--slate)]">
              {PLAN_CONTENT.taglines[plan.plan]}
            </p>

            <p className="mt-5 flex items-baseline gap-1.5">
              <span className="font-[family-name:var(--font-display)] text-[40px] leading-none tabular-nums text-[var(--ink)]">
                {formatPlanPrice(price)}
              </span>
              <span className="text-[13px] text-[var(--slate)]">
                / {interval === "monthly" ? "month" : "year"}
              </span>
            </p>
            <p className="mt-2 min-h-4 font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)]">
              {interval === "annual" && saving > 0
                ? `Save ${formatMoney(saving)} per year (${Math.round(
                    (saving / (plan.monthly_price_cents * 12)) * 100,
                  )}%)`
                : " "}
            </p>

            <div className="mt-5 flex items-baseline justify-between rounded-[2px] bg-[var(--mist)] px-3 py-2.5">
              <span className="font-[family-name:var(--font-mono)] text-sm tabular-nums text-[var(--ink)]">
                {plan.monthly_credits.toLocaleString()}
              </span>
              <span className="text-xs text-[var(--slate)]">credits every month</span>
            </div>

            <ul className="mt-5 space-y-2.5 text-sm text-[var(--slate)]">
              {PLAN_CONTENT.features[plan.plan].map((feature) => (
                <li key={feature} className="flex gap-2.5">
                  <Check />
                  {feature}
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-6">{action(plan)}</div>
          </article>
        );
      })}
    </div>
  );
}
