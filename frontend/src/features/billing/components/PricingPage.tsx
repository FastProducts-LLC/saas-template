// Public pricing page shown at "/pricing". Renders outside AppLayout with the
// shared marketing chrome (pill nav + footer) from the home feature. Packs
// come from useCreditPacks() — the single source of truth — never hardcoded.

import { useState } from "react";
import { PLAN_CONTENT } from "../../../shared/content/marketing";
import { usePlans } from "../api/hooks";
import type { BillingInterval } from "../model/types";
import PlanCards from "./PlanCards";
import PlanIntervalToggle from "./PlanIntervalToggle";
import { Link } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { formatMoney } from "../../../shared/lib/money";
import { Button, Spinner, Stamp, ErrorAlert } from "../../../shared/ui";
import { useAuth } from "../../auth";
import { PackDiscountStamp, PackGrid, useCreditPacks } from "../../credits";
import { MarketingFooter, MarketingHeader } from "../../home";

export default function PricingPage() {
  const { user } = useAuth();
  const plans = usePlans();
  const [interval, setInterval] = useState<BillingInterval>("monthly");
  const { data: creditPacks = [] } = useCreditPacks();

  const ctaTo = user ? ROUTES.billing : ROUTES.auth.register;

  return (
    <div
      data-testid="pricing-page"
      className="min-h-screen bg-[var(--paper)] text-[var(--ink)] antialiased"
    >
      <MarketingHeader />

      <main>
        {/* Hero — same soft glow + grid backdrop as the home page */}
        <section className="relative isolate overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(ellipse 70% 55% at 50% 0%, color-mix(in srgb, var(--lime) 30%, transparent), transparent 60%)",
            }}
          />
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.5]"
            style={{
              backgroundImage: `
                linear-gradient(color-mix(in srgb, var(--ink) 4.5%, transparent) 1px, transparent 1px),
                linear-gradient(90deg, color-mix(in srgb, var(--ink) 4.5%, transparent) 1px, transparent 1px)
              `,
              backgroundSize: "48px 48px",
              maskImage: "radial-gradient(ellipse 75% 70% at 50% 10%, black, transparent)",
            }}
            aria-hidden="true"
          />
          <div className="relative mx-auto max-w-6xl px-6 pb-16 pt-36 text-center sm:pt-40">
            <p className="gd-hero-in text-sm font-medium text-[var(--slate)]/80">Pricing</p>
            <h1
              className="gd-hero-in mx-auto mt-3 max-w-2xl font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl"
              style={{ animationDelay: "0.08s" }}
            >
              {PLAN_CONTENT.heading}
            </h1>
            <p
              className="gd-hero-in mx-auto mt-5 max-w-xl text-base text-[var(--slate)] sm:text-lg"
              style={{ animationDelay: "0.16s" }}
            >
              {PLAN_CONTENT.description}
            </p>
          </div>
        </section>

        <section aria-label="Plans" className="mx-auto max-w-6xl px-6 pb-12">
          <PlanIntervalToggle value={interval} onChange={setInterval} />
          {plans.isLoading && <Spinner className="h-5 w-5" />}
          <ErrorAlert error={plans.error} />
          {plans.data?.length === 0 && <p>No plans available.</p>}
          {plans.data && (
            <PlanCards
              plans={plans.data}
              interval={interval}
              action={(plan) => (
                <Link
                  className="inline-block rounded bg-[var(--ink)] px-4 py-2 text-sm font-medium text-white"
                  to={ctaTo}
                  aria-label={`${user ? PLAN_CONTENT.signedIn : PLAN_CONTENT.signedOut} — ${plan.name}`}
                >
                  {user ? PLAN_CONTENT.signedIn : PLAN_CONTENT.signedOut}
                </Link>
              )}
            />
          )}
        </section>

        <section className="border-y border-[var(--line)] bg-white">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="text-center">
              <h2
                className="gd-hero-in font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-[var(--ink)]"
                style={{ animationDelay: "0.24s" }}
              >
                Credit top-ups
              </h2>
              <p
                className="gd-hero-in mx-auto mt-3 max-w-lg text-base text-[var(--slate)]"
                style={{ animationDelay: "0.32s" }}
              >
                One-time top-ups with volume discounts — the more you buy, the less each lookup
                costs. Identity checks are always free; credits unlock search and full profiles.
              </p>
            </div>

            <div className="mt-12 border-t border-[var(--line)]">
              <PackGrid count={creditPacks.length}>
                {creditPacks.map((p, i) => (
                  <div
                    key={p.pack}
                    data-testid="pricing-pack"
                    data-id={p.pack}
                    className={`px-5 py-5 ${i > 0 ? "border-t border-[var(--line)] sm:border-l sm:border-t-0" : ""}`}
                  >
                    <PackDiscountStamp pct={p.discount_pct} className="mb-3" />
                    <p className="font-[family-name:var(--font-display)] text-[40px] font-bold leading-none text-[var(--ink)] tabular-nums">
                      {formatMoney(p.price_cents, { fractionDigits: 0 })}
                    </p>
                    <p className="mt-2 font-[family-name:var(--font-mono)] text-sm text-[var(--ink)] tabular-nums">
                      {p.credits.toLocaleString()} credits
                    </p>
                    <p className="mt-1 font-[family-name:var(--font-mono)] text-xs text-[var(--slate)] tabular-nums">
                      {formatMoney(p.unit_price_cents)}/credit
                    </p>
                  </div>
                ))}
              </PackGrid>
            </div>

            <p className="mt-6 text-center text-sm text-[var(--slate)]/80">
              Credits never expire. Purchased once — use any time.
            </p>

            <div className="mt-8 text-center">
              <Link to={ctaTo}>
                <Button data-testid="pricing-cta-button" className="px-8">
                  {user ? "Buy credits" : "Start free"}
                </Button>
              </Link>
              <p className="mt-3 text-xs text-[var(--slate)]/65">
                No credit card required to start — instant identity checks are free.
              </p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20">
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 rounded border border-dashed border-[var(--line)] bg-white px-8 py-10 text-center">
            <div className="flex items-center gap-2">
              <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-[var(--ink)]">
                Enterprise
              </h2>
              <Stamp className="border-[var(--line)] text-[var(--slate)]/60">Coming soon</Stamp>
            </div>
            <p className="max-w-md text-sm text-[var(--slate)]">
              Volume pricing, invoicing, dedicated support, and custom terms for high-volume teams.
            </p>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
