import { useEffect, useState, type CSSProperties, type SVGProps } from "react";
import { Link } from "react-router-dom";

import { OnboardingTour, type OnboardingStep } from "../../../components/OnboardingTour";
import { useTour } from "../../../components/useTour";
import { EVENTS } from "../../../shared/lib/events";
import { ROUTES } from "../../../shared/lib/routes";
import { TOUR_KEYS } from "../../../shared/lib/tours";
import { track } from "../../../shared/lib/track";
import { Counter, CounterStrip, PageHeader, SectionRule, Stamp } from "../../../shared/ui";
import { BRAND } from "../../../shared/lib/brand";
import { useAuth } from "../../auth";
import { useBillingPlan, usePlans } from "../../billing";
import {
  TYPE_LABELS,
  TYPE_STYLES,
  actionLabel,
  currentPeriodUTC,
  useCreditHistory,
  useCreditUsage,
  useWallet,
  type CreditTransaction,
} from "../../credits";
import { useOrg } from "../../organizations";

function tourIcon(props: SVGProps<SVGSVGElement>): SVGProps<SVGSVGElement> {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
    className: "h-5 w-5",
    ...props,
  };
}

const DASHBOARD_TOUR: OnboardingStep[] = [
  {
    id: "welcome",
    title: `Welcome to ${BRAND}`,
    description: "Let's take a quick tour of the key features so you can get started fast.",
    icon: (
      <svg {...tourIcon({})}>
        <path d="M12 3l1.5 4.5H18l-3.5 2.7 1.3 4.3L12 12l-3.8 2.5 1.3-4.3L6 7.5h4.5z" />
      </svg>
    ),
    placement: "center",
  },
  {
    id: "org-switcher",
    title: "Organization switcher",
    description:
      "Switch between organizations you belong to, or create a new one. All data, billing, and members are scoped per org.",
    icon: (
      <svg {...tourIcon({})}>
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
    selector: "[data-tour='org-switcher']",
    placement: "right",
  },
  {
    id: "stats",
    title: "Your account at a glance",
    description:
      "See your credit balance and this month's spend — metered actions hold credits up front and settle when they finish.",
    icon: (
      <svg {...tourIcon({})}>
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
    selector: "[data-tour='stats-grid']",
    placement: "bottom",
  },
  {
    id: "api-cta",
    title: "Build with the API",
    description:
      "Create an API key and call the metered endpoints programmatically — usage is attributed to the key, not a member.",
    icon: (
      <svg {...tourIcon({})}>
        <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
      </svg>
    ),
    selector: "[data-tour='api-cta']",
    placement: "top",
  },
  {
    id: "nav-billing",
    title: "Billing & credits",
    description: "Purchase credit packs and view invoices — all in one place.",
    icon: (
      <svg {...tourIcon({})}>
        <rect x="2.5" y="5" width="19" height="14" rx="2" />
        <line x1="2.5" y1="10" x2="21.5" y2="10" />
      </svg>
    ),
    selector: "[data-tour='nav-billing']",
    placement: "right",
  },
  {
    id: "done",
    title: "You're all set!",
    description:
      "Head to Billing to grab credits, or the API docs to make your first call. You can replay this tour anytime from Settings.",
    icon: (
      <svg {...tourIcon({})}>
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
    ),
    placement: "center",
  },
];

function CountUp({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const raf = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(raf);
    }
    let raf = 0;
    const duration = 900;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(value * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <>{display.toLocaleString()}</>;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function transactionSummary(tx: CreditTransaction): string {
  const actor = tx.user_email ?? tx.api_key_name;
  const bits = [tx.description || actionLabel(tx.action) || TYPE_LABELS[tx.type], actor];
  return bits.filter(Boolean).join(" · ");
}

function relativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(iso).toLocaleDateString();
}

function Arrow({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}

const SHORTCUTS = [
  { to: ROUTES.members, label: "Invite teammates", detail: "Members share one credit balance" },
  { to: ROUTES.billing, label: "Plans and credit packs", detail: "Upgrade or top up" },
  { to: ROUTES.settings, label: "Organization settings", detail: "Name, domain, and access" },
] as const;

export default function DashboardPage() {
  const { user } = useAuth();
  const { currentOrg } = useOrg();
  const { data: wallet } = useWallet(currentOrg?.id);
  const { data: usage } = useCreditUsage(currentOrg?.id, currentPeriodUTC());
  const { data: history, isLoading: historyLoading } = useCreditHistory(currentOrg?.id, 0);
  const { data: plans } = usePlans();
  const { data: billingPlan } = useBillingPlan(currentOrg?.id);
  const tour = useTour(TOUR_KEYS.dashboard, DASHBOARD_TOUR);

  const recentTransactions = history?.items.slice(0, 8) ?? [];
  const firstName = user?.name?.split(" ")[0];
  const planKey = billingPlan?.subscription?.plan ?? billingPlan?.plan;
  const planName = plans?.find((p) => p.plan === planKey)?.name ?? planKey;

  return (
    <div className="max-w-[1200px]" data-testid="dashboard-page">
      <OnboardingTour
        {...tour}
        onComplete={() => {
          track(EVENTS.onboarding_tour_completed, { tour: "dashboard" });
          tour.onComplete();
        }}
        onClose={() => {
          track(EVENTS.onboarding_tour_skipped, { tour: "dashboard" });
          tour.onClose();
        }}
      />

      <div className="gd-stagger-item" style={{ "--i": 0 } as CSSProperties}>
        <PageHeader
          titleTestId="dashboard-greeting"
          title={`${greeting()}, ${firstName}`}
          meta={`${currentOrg?.name ?? ""} · ${capitalize(currentOrg?.role ?? "")}`}
          actions={
            <Link
              to={ROUTES.billing}
              data-testid="dashboard-buy-credits-link"
              className="gd-press inline-flex items-center gap-2 rounded bg-[var(--ink)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--ink-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal)]/30"
            >
              Buy credits
            </Link>
          }
        />
      </div>

      {/* Counters */}
      <div
        data-tour="stats-grid"
        data-testid="dashboard-stats"
        className="gd-stagger-item mt-8"
        style={{ "--i": 1 } as CSSProperties}
      >
        <CounterStrip>
          <Counter
            to={ROUTES.billing}
            linkTestId="dashboard-credits-link"
            testId="dashboard-credits-value"
            value={wallet ? <CountUp value={wallet.balance} /> : "—"}
            label="Credits available"
            detail={
              wallet && wallet.reserved > 0
                ? `${wallet.reserved.toLocaleString()} on hold`
                : undefined
            }
          />
          {(!wallet || wallet.monthly_allowance > 0) && (
            <Counter
              to={ROUTES.billing}
              linkTestId="dashboard-allowance-link"
              testId="dashboard-allowance-value"
              value={wallet ? <CountUp value={wallet.monthly_allowance} /> : "—"}
              label="Added every month"
            />
          )}
          <Counter
            testId="dashboard-spent-value"
            value={usage ? <CountUp value={usage.total_credits} /> : "—"}
            label="Spent this month"
            detail={
              usage && usage.total_actors > 0
                ? `across ${usage.total_actors} ${usage.total_actors === 1 ? "member or key" : "members and keys"}`
                : undefined
            }
          />
          <Counter
            to={ROUTES.billing}
            linkTestId="dashboard-plan-link"
            testId="dashboard-plan-value"
            value={planName ?? "—"}
            label="Current plan"
          />
        </CounterStrip>
      </div>

      <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {/* Recent activity — credit ledger */}
        <section
          data-tour="recent-activity"
          className="gd-stagger-item min-w-0"
          style={{ "--i": 2 } as CSSProperties}
          aria-label="Recent activity"
        >
          <SectionRule
            index="01"
            title="Recent activity"
            action={
              <Link
                to={ROUTES.billing}
                data-testid="dashboard-view-all-link"
                className="inline-flex items-center gap-1 text-xs font-medium text-[var(--ink)] hover:underline"
              >
                View all <Arrow className="h-3 w-3" />
              </Link>
            }
          />

          <div className="mt-3 overflow-hidden rounded border border-[var(--line)] bg-white">
            {historyLoading && (
              <div
                data-testid="dashboard-loading"
                className="divide-y divide-[var(--line)]"
                aria-label="Loading recent activity"
              >
                {[0, 1, 2].map((i) => (
                  <div key={i} className="flex h-10 items-center gap-3 px-4">
                    <div className="gd-skel h-3 w-12" />
                    <div className="gd-skel h-3 max-w-48 flex-1" />
                    <div className="gd-skel ml-auto h-3 w-14" />
                  </div>
                ))}
              </div>
            )}
            {!historyLoading && !recentTransactions.length && (
              <div data-testid="dashboard-empty" className="relative">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    aria-hidden
                    className="h-10 border-b border-dashed border-[var(--line)] last:border-b-0"
                  />
                ))}
                <p className="absolute inset-0 flex items-center justify-center bg-white/70 px-4 text-center text-sm text-[var(--slate)]">
                  No activity yet. Credit grants and spends will show up here.
                </p>
              </div>
            )}
            {!!recentTransactions.length && (
              <table data-testid="dashboard-table" className="w-full table-fixed text-left">
                <thead>
                  <tr className="h-10 bg-[var(--mist)] font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-normal text-[var(--slate)]">
                    <th className="w-36 px-4 py-2 font-medium">Type</th>
                    <th className="px-4 py-2 font-medium">Detail</th>
                    <th className="w-20 px-4 py-2 text-right font-medium">Credits</th>
                    <th className="w-24 px-4 py-2 text-right font-medium">When</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTransactions.map((tx, i) => (
                    <tr
                      key={tx.id}
                      data-testid="dashboard-row"
                      data-id={tx.id}
                      className="gd-row-in h-10 border-t border-[var(--line)] text-[13px] transition-colors hover:bg-[var(--paper)]"
                      style={{ "--i": i } as CSSProperties}
                    >
                      <td className="px-4 py-2">
                        <Stamp className={`whitespace-nowrap ${TYPE_STYLES[tx.type]}`}>
                          {TYPE_LABELS[tx.type]}
                        </Stamp>
                      </td>
                      <td className="max-w-0 truncate px-4 py-2 font-[family-name:var(--font-mono)] text-[var(--ink)]">
                        {transactionSummary(tx)}
                      </td>
                      <td className="px-4 py-2 text-right font-[family-name:var(--font-mono)] text-[var(--ink)] tabular-nums">
                        {tx.amount > 0 ? "+" : ""}
                        {tx.amount.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right font-[family-name:var(--font-mono)] text-[var(--slate)] tabular-nums">
                        {relativeTime(tx.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Side rail */}
        <aside
          className="gd-stagger-item space-y-8"
          style={{ "--i": 3 } as CSSProperties}
          aria-label="Next steps"
        >
          <section
            data-tour="api-cta"
            className="rounded border border-[var(--sand-line)] bg-[var(--sand)] p-5"
          >
            <p className="font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-[0.08em] text-[var(--slate)]">
              Developers
            </p>
            <h2 className="mt-2 text-[17px] font-semibold text-[var(--ink)]">Build with the API</h2>
            <p className="mt-1 text-sm leading-relaxed text-[var(--slate)]">
              Create an API key and call the metered endpoints from your own code. Usage is billed
              to this organization.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Link
                to={ROUTES.apiKeys}
                data-testid="dashboard-api-keys-link"
                className="gd-press inline-flex items-center gap-2 rounded border border-[var(--ink)]/15 bg-white px-3 py-1.5 text-[13px] font-medium text-[var(--ink)] transition-colors hover:border-[var(--ink)]/40"
              >
                Create an API key <Arrow className="h-3 w-3" />
              </Link>
              <Link
                to={ROUTES.docs}
                data-testid="dashboard-docs-link"
                className="text-[13px] font-medium text-[var(--ink)] hover:underline"
              >
                Read the docs
              </Link>
            </div>
          </section>

          <section aria-label="Shortcuts">
            <SectionRule index="02" title="Shortcuts" />
            <ul className="mt-2 divide-y divide-[var(--line)]">
              {SHORTCUTS.map((item) => (
                <li key={item.to}>
                  <Link to={item.to} className="group flex items-center justify-between gap-3 py-3">
                    <span>
                      <span className="block text-sm font-medium text-[var(--ink)]">
                        {item.label}
                      </span>
                      <span className="block text-xs text-[var(--slate)]">{item.detail}</span>
                    </span>
                    <Arrow className="h-3.5 w-3.5 text-[var(--slate)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--ink)]" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}

function capitalize(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}
