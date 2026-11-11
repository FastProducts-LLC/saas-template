import { useState, type ReactNode } from "react";
import { isApiErrorWithCode } from "../../../shared/api";
import { PLAN_CONTENT } from "../../../shared/content/marketing";
import { Alert, Button, ErrorAlert, SectionRule, Spinner, Stamp } from "../../../shared/ui";
import { useBillingPlan, useBillingPortal, usePlanCheckout, usePlans } from "../api/hooks";
import type { BillingInterval } from "../model/types";
import { formatPlanPrice } from "../model/format";
import PlanCards from "./PlanCards";
import PlanIntervalToggle from "./PlanIntervalToggle";

const STATUS_TONE: Record<string, string> = {
  active: "border-[var(--success)] text-[var(--success)]",
  trialing: "border-[var(--info)] text-[var(--info)]",
  past_due: "border-[var(--danger)] text-[var(--danger)]",
};

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <dt className="text-[13px] text-[var(--slate)]">{label}</dt>
      <dd className="font-[family-name:var(--font-mono)] text-[13px] tabular-nums text-[var(--ink)]">
        {children}
      </dd>
    </div>
  );
}

// The organization's plan: a summary panel in the billing overview (beside
// `aside`, the credit balance) and the plan picker as section 01.
export default function PlanSection({
  orgId,
  admin,
  aside,
}: {
  orgId: string;
  admin: boolean;
  aside?: ReactNode;
}) {
  const catalog = usePlans();
  const overview = useBillingPlan(orgId);
  const checkout = usePlanCheckout(orgId);
  const portal = useBillingPortal(orgId);
  const [interval, setInterval] = useState<BillingInterval>("monthly");
  const subscription = overview.data?.subscription;
  const live = subscription && ["trialing", "active", "past_due"].includes(subscription.status);
  const alreadyActive = isApiErrorWithCode(checkout.error, "ERR_BILL_009");
  const error = catalog.error ?? overview.error ?? checkout.error ?? portal.error;
  const date = subscription?.current_period_end
    ? new Date(subscription.current_period_end).toLocaleDateString()
    : "Not available";
  const currentPlanKey = live ? subscription.plan : overview.data?.plan;
  const currentPlan = catalog.data?.find((p) => p.plan === currentPlanKey);
  const portalBusy = portal.isPending || portal.isSuccess;
  const manage = (label: string, variant: "primary" | "secondary" = "secondary") => (
    <Button variant={variant} disabled={portalBusy} onClick={() => portal.mutate()}>
      {label}
    </Button>
  );
  const subscribed = live || alreadyActive;

  return (
    <>
      <section aria-label="Organization plan" className="space-y-3">
        <ErrorAlert error={error} />
        <div className="grid gap-3 lg:grid-cols-2">
          <div
            data-testid="plan-summary"
            className="flex flex-col rounded border border-[var(--line)] bg-white p-6"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-[0.08em] text-[var(--slate)]">
                Current plan
              </p>
              {live && (
                <Stamp className={STATUS_TONE[subscription.status] ?? ""}>
                  {subscription.status}
                </Stamp>
              )}
            </div>

            {(catalog.isLoading || overview.isLoading) && <Spinner className="mt-4 h-5 w-5" />}
            {overview.data && (
              <>
                <p
                  data-testid="plan-current-name"
                  className="mt-3 font-[family-name:var(--font-display)] text-[36px] leading-none text-[var(--ink)]"
                >
                  {currentPlan?.name ?? overview.data.plan}
                </p>
                {currentPlan && (
                  <p className="mt-2 text-sm text-[var(--slate)]">
                    {live && subscription.interval === "annual"
                      ? `${formatPlanPrice(currentPlan.annual_price_cents)} / year`
                      : `${formatPlanPrice(currentPlan.monthly_price_cents)} / month`}
                    {" · "}
                    {PLAN_CONTENT.taglines[currentPlan.plan]}
                  </p>
                )}

                <dl className="mt-5 divide-y divide-[var(--line)] border-y border-[var(--line)]">
                  {currentPlan && (
                    <Row label="Credits per month">
                      {currentPlan.monthly_credits.toLocaleString()}
                    </Row>
                  )}
                  {live ? (
                    <>
                      <Row label="Billing">
                        {subscription.interval === "annual" ? "Annual" : "Monthly"}
                      </Row>
                      <Row
                        label={subscription.status === "trialing" ? "Trial ends" : "Renewal date"}
                      >
                        {date}
                      </Row>
                    </>
                  ) : (
                    <Row label="Billing">No subscription</Row>
                  )}
                </dl>
              </>
            )}

            {live && subscription.cancel_at_period_end && (
              <Alert tone="info" className="mt-4">
                Your plan ends on {date}.
              </Alert>
            )}
            {live && subscription.status === "past_due" && (
              <Alert tone="warning" className="mt-4">
                <p>Payment failed. Access continues for a limited time.</p>
                {admin && <div className="mt-2">{manage("Update payment method", "primary")}</div>}
              </Alert>
            )}

            <div className="mt-auto flex flex-wrap items-center gap-3 pt-5">
              {admin && subscribed && manage("Manage plan")}
              {admin && !subscribed && overview.data && !!catalog.data?.length && (
                <a
                  href="#plans"
                  className="text-sm font-medium text-[var(--ink)] underline-offset-4 hover:underline"
                >
                  Compare plans ↓
                </a>
              )}
              {!admin && (
                <p className="text-xs text-[var(--slate)]">
                  Only owners and admins can change the plan.
                </p>
              )}
            </div>
          </div>
          {aside}
        </div>
      </section>

      {overview.data && catalog.data && (
        <section aria-label="Choose a plan" className="mt-12">
          <SectionRule
            id="plans"
            index="01"
            title="Plans"
            action={<PlanIntervalToggle value={interval} onChange={setInterval} />}
          />
          <p className="mt-2 text-sm text-[var(--slate)]">{PLAN_CONTENT.description}</p>
          {catalog.data.length === 0 ? (
            <p className="mt-4 text-sm text-[var(--slate)]">No plans available.</p>
          ) : (
            <div className="mt-5">
              <PlanCards
                plans={catalog.data}
                interval={interval}
                currentPlan={currentPlanKey}
                action={(plan) => {
                  if (!admin) return null;
                  if (plan.plan === currentPlanKey) {
                    return (
                      <p className="flex h-9 items-center justify-center rounded border border-dashed border-[var(--line)] text-xs text-[var(--slate)]">
                        Your current plan
                      </p>
                    );
                  }
                  if (subscribed) {
                    return (
                      <Button
                        variant="secondary"
                        className="w-full"
                        disabled={portalBusy}
                        onClick={() => portal.mutate()}
                      >
                        Switch to {plan.name}
                      </Button>
                    );
                  }
                  if (plan.plan === "free") return null;
                  const available = plan.purchasable[interval];
                  return (
                    <div className="space-y-2">
                      <Button
                        variant={
                          available && plan.plan === PLAN_CONTENT.recommended
                            ? "primary"
                            : "secondary"
                        }
                        className="w-full"
                        disabled={!available || checkout.isPending || checkout.isSuccess}
                        onClick={() => checkout.mutate({ plan: plan.plan, interval })}
                      >
                        Subscribe to {plan.name}
                      </Button>
                      {!available && (
                        <p className="text-center text-xs text-[var(--slate)]">
                          This billing interval is currently unavailable.
                        </p>
                      )}
                    </div>
                  );
                }}
              />
            </div>
          )}
        </section>
      )}
    </>
  );
}
