import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ROUTES } from "../../shared/lib/routes";
import { Sparkline } from "../../shared/ui";
import {
  fetchAnalytics,
  fetchStats,
  type CategoryCount,
  type TimeseriesPoint,
  type TopCustomer,
} from "./api";

const numberFormatter = new Intl.NumberFormat("en-US");
const decimalFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
});
const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 1,
});

function sum(points: TimeseriesPoint[] | undefined): number | undefined {
  return points?.reduce((s, p) => s + p.count, 0);
}

function sumCounts(rows: CategoryCount[] | undefined): number {
  return rows?.reduce((s, row) => s + row.count, 0) ?? 0;
}

function countFor(rows: CategoryCount[] | undefined, label: string): number {
  return rows?.find((row) => row.label === label)?.count ?? 0;
}

function recentSum(points: TimeseriesPoint[] | undefined, days: number): number | undefined {
  if (!points) return undefined;
  return points.slice(-days).reduce((s, point) => s + point.count, 0);
}

function previousSum(points: TimeseriesPoint[] | undefined, days: number): number | undefined {
  if (!points || points.length <= days) return undefined;
  return points.slice(-days * 2, -days).reduce((s, point) => s + point.count, 0);
}

function formatNumber(value: number | undefined | null): string {
  return value == null ? "—" : numberFormatter.format(value);
}

function formatDecimal(value: number | undefined | null): string {
  return value == null || !Number.isFinite(value) ? "—" : decimalFormatter.format(value);
}

function formatPercent(numerator: number | undefined, denominator: number | undefined): string {
  if (numerator == null || denominator == null || denominator <= 0) return "—";
  return percentFormatter.format(numerator / denominator);
}

function trendContext(current: number | undefined, previous: number | undefined): string {
  if (current == null) return "Waiting for trend data";
  if (previous == null) return `${formatNumber(current)} in the last 7 days`;
  if (previous === 0) return `${formatNumber(current)} in the last 7 days`;
  const delta = current - previous;
  const direction = delta >= 0 ? "up" : "down";
  return `${direction} ${formatPercent(Math.abs(delta), previous)} vs prior 7 days`;
}

function generationKindLabel(label: string): string {
  switch (label) {
    case "image_nano_banana":
      return "Nano Banana images";
    case "image_gpt":
      return "GPT images";
    case "video_veo":
      return "VEO videos";
    case "llm_call":
      return "LLM calls";
    default:
      return label.replaceAll("_", " ");
  }
}

function statusLabel(label: string): string {
  return label.charAt(0).toUpperCase() + label.slice(1);
}

type MetricTone = "neutral" | "success" | "warning" | "danger";

type MetricPanelItem = {
  label: string;
  value: number | undefined;
  detail?: string;
  tone?: MetricTone;
};

const metricToneClass: Record<MetricTone, string> = {
  neutral: "bg-[var(--paper)] text-[var(--slate)]",
  success: "border border-[var(--success)] text-[var(--success)]",
  warning: "border border-[var(--danger)] text-[var(--danger)]",
  danger: "border border-[var(--danger)] text-[var(--danger)]",
};

function issueTone(value: number | undefined): MetricTone {
  if (value == null) return "neutral";
  return value > 0 ? "danger" : "success";
}

function warningTone(value: number | undefined): MetricTone {
  if (value == null) return "neutral";
  return value > 0 ? "warning" : "success";
}

function StatCard({
  label,
  value,
  detail,
  testId,
  dataId,
}: {
  label: string;
  value: number | undefined;
  detail: string;
  testId: string;
  dataId: string;
}) {
  return (
    <div
      data-testid={testId}
      data-id={dataId}
      className="rounded-xl border border-[var(--mist)] bg-white p-4"
    >
      <p className="text-sm text-[var(--slate)]/75">{label}</p>
      <p className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)] tabular-nums">
        {formatNumber(value)}
      </p>
      <p className="mt-2 text-xs text-[var(--slate)]/60">{detail}</p>
    </div>
  );
}

function TrendCard({
  label,
  total,
  points,
  context,
  testId,
}: {
  label: string;
  total: number | undefined;
  points: TimeseriesPoint[] | undefined;
  context: string;
  testId: string;
}) {
  return (
    <div data-testid={testId} className="rounded-xl border border-[var(--mist)] bg-white p-4">
      <p className="text-sm text-[var(--slate)]/75">{label}</p>
      <div className="mt-1 flex items-end justify-between gap-3">
        <p className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)] tabular-nums">
          {formatNumber(total)}
        </p>
        {points && points.length > 1 && (
          <Sparkline data={points.map((p) => p.count)} data-testid={`${testId}-spark`} />
        )}
      </div>
      <p className="mt-1 text-xs text-[var(--slate)]/55">{context}</p>
    </div>
  );
}

function SignalCard({
  label,
  value,
  detail,
  to,
  testId,
}: {
  label: string;
  value: string;
  detail: string;
  to: string;
  testId: string;
}) {
  return (
    <Link
      to={to}
      data-testid={testId}
      className="rounded-xl border border-[var(--mist)] bg-white p-4 transition-colors hover:border-[var(--teal)]/45 hover:bg-[var(--teal)]/5"
    >
      <p className="text-sm text-[var(--slate)]/75">{label}</p>
      <p className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)] tabular-nums">
        {value}
      </p>
      <p className="mt-2 text-xs text-[var(--slate)]/60">{detail}</p>
    </Link>
  );
}

function BreakdownPanel({
  title,
  rows,
  emptyLabel,
  labelFor,
  testId,
}: {
  title: string;
  rows: CategoryCount[];
  emptyLabel: string;
  labelFor: (label: string) => string;
  testId: string;
}) {
  const total = sumCounts(rows);

  return (
    <div data-testid={testId} className="rounded-xl border border-[var(--mist)] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--ink)]">{title}</p>
          <p className="mt-1 text-xs text-[var(--slate)]/60">last 30 days</p>
        </div>
        <span className="font-[family-name:var(--font-mono)] text-sm text-[var(--slate)] tabular-nums">
          {formatNumber(total)}
        </span>
      </div>

      {total > 0 ? (
        <ul className="mt-4 space-y-3 text-sm text-[var(--slate)]">
          {rows.map((row) => {
            const width = `${Math.max((row.count / total) * 100, 3)}%`;
            return (
              <li key={row.label}>
                <div className="flex items-center justify-between gap-3">
                  <span>{labelFor(row.label)}</span>
                  <span className="font-[family-name:var(--font-mono)] tabular-nums">
                    {formatNumber(row.count)} ({formatPercent(row.count, total)})
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--mist)]">
                  <div className="h-full rounded-full bg-[var(--teal-deep)]" style={{ width }} />
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-[var(--slate)]/55">{emptyLabel}</p>
      )}
    </div>
  );
}

function TopCustomersPanel({
  customers,
  capturedCredits,
}: {
  customers: TopCustomer[];
  capturedCredits: number | undefined;
}) {
  const maxValue = Math.max(...customers.map((customer) => customer.value), 0);

  return (
    <div
      data-testid="admin-overview-top-customers"
      className="rounded-xl border border-[var(--mist)] bg-white p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--ink)]">Top customers by credits</p>
          <p className="mt-1 text-xs text-[var(--slate)]/60">all-time captured credits</p>
        </div>
        <Link to={ROUTES.admin.customers} className="text-sm font-medium text-[var(--teal-deep)]">
          View
        </Link>
      </div>

      {customers.length > 0 ? (
        <ul className="mt-4 space-y-3 text-sm text-[var(--slate)]">
          {customers.map((customer) => {
            const width =
              maxValue > 0 ? `${Math.max((customer.value / maxValue) * 100, 3)}%` : "0%";
            return (
              <li key={customer.name}>
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate">{customer.name}</span>
                  <span className="font-[family-name:var(--font-mono)] tabular-nums">
                    {formatNumber(customer.value)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--mist)]">
                  <div className="h-full rounded-full bg-[var(--ink)]" style={{ width }} />
                </div>
                <p className="mt-1 text-xs text-[var(--slate)]/55">
                  {formatPercent(customer.value, capturedCredits)} of captured credits
                </p>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-[var(--slate)]/55">No captured credit usage yet.</p>
      )}
    </div>
  );
}

function MetricPanel({
  title,
  subtitle,
  items,
  testId,
  actionTo,
  emptyLabel,
}: {
  title: string;
  subtitle: string;
  items: MetricPanelItem[];
  testId: string;
  actionTo?: string;
  emptyLabel?: string;
}) {
  return (
    <div data-testid={testId} className="rounded-xl border border-[var(--mist)] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--ink)]">{title}</p>
          <p className="mt-1 text-xs text-[var(--slate)]/60">{subtitle}</p>
        </div>
        {actionTo && (
          <Link to={actionTo} className="text-sm font-medium text-[var(--teal-deep)]">
            Open
          </Link>
        )}
      </div>

      {items.length > 0 ? (
        <ul className="mt-4 divide-y divide-[var(--mist)] text-sm">
          {items.map((item) => (
            <li key={item.label} className="flex items-start justify-between gap-3 py-2 first:pt-0">
              <div className="min-w-0">
                <p className="font-medium text-[var(--ink)]">{item.label}</p>
                {item.detail && (
                  <p className="mt-0.5 text-xs text-[var(--slate)]/60">{item.detail}</p>
                )}
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 font-[family-name:var(--font-mono)] text-xs tabular-nums ${
                  metricToneClass[item.tone ?? "neutral"]
                }`}
              >
                {formatNumber(item.value)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-[var(--slate)]/55">
          {emptyLabel ?? "No records for this period."}
        </p>
      )}
    </div>
  );
}

const workflowLinks = [
  {
    to: ROUTES.admin.customers,
    label: "Customer revenue",
    detail: "Owners, duplicate orgs, credits spent, and estimated dollars.",
  },
  {
    to: ROUTES.admin.credits,
    label: "Credit risk",
    detail: "Wallet balances, pending holds, allowance periods, and manual adjustments.",
  },
  {
    to: ROUTES.admin.generations,
    label: "Generation health",
    detail: "Failed jobs, pending work, model mix, prompt context, and credit cost.",
  },
  {
    to: ROUTES.admin.users,
    label: "Account control",
    detail: "Active state, session revocation, impersonation, and org membership count.",
  },
  {
    to: ROUTES.admin.audit,
    label: "Admin audit",
    detail: "Superuser actions across credits, users, invitations, and organizations.",
  },
  {
    to: ROUTES.admin.privacyRequests,
    label: "Privacy requests",
    detail: "Data access, deletion, export, and verification workflows.",
  },
];

export default function AdminOverviewPage() {
  const { data: stats } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: fetchStats,
  });
  const { data: analytics } = useQuery({
    queryKey: ["admin", "analytics"],
    queryFn: fetchAnalytics,
  });

  const cards = [
    {
      key: "total_users",
      label: "Total users",
      value: stats?.total_users,
      detail: `${formatPercent(stats?.active_users, stats?.total_users)} active`,
    },
    {
      key: "active_users",
      label: "Active users",
      value: stats?.active_users,
      detail:
        stats == null
          ? "Waiting for user stats"
          : `${formatNumber(stats.total_users - stats.active_users)} inactive accounts`,
    },
    {
      key: "total_organizations",
      label: "Organizations",
      value: stats?.total_organizations,
      detail: `${formatDecimal(
        stats && stats.total_organizations > 0
          ? stats.total_users / stats.total_organizations
          : undefined,
      )} users per org`,
    },
  ];

  const creditCards = [
    {
      key: "total_balance",
      label: "Credits in wallets",
      value: analytics?.credit_summary.total_balance,
      detail: "outstanding customer balance",
    },
    {
      key: "total_pending_holds",
      label: "Pending holds",
      value: analytics?.credit_summary.total_pending_holds,
      detail: "reservations awaiting capture or release",
    },
    {
      key: "total_credits_captured",
      label: "Credits captured (all time)",
      value: analytics?.credit_summary.total_credits_captured,
      detail: "settled usage across all customers",
    },
  ];

  const generations = analytics?.generations_by_status ?? [];
  const generationKinds = analytics?.generations_by_kind ?? [];
  const topCustomers = analytics?.top_customers_by_credits ?? [];
  const commercial = analytics?.commercial_summary;
  const operations = analytics?.operations_summary;
  const security = analytics?.security_summary;
  const recentAdminActions = analytics?.recent_admin_actions ?? [];
  const generationTotal = sumCounts(generations);
  const failedGenerations = countFor(generations, "failed");
  const pendingGenerations = countFor(generations, "pending");
  const topCustomerCredits = topCustomers.reduce((total, customer) => total + customer.value, 0);
  const capturedCredits = analytics?.credit_summary.total_credits_captured;
  const walletBalance = analytics?.credit_summary.total_balance;
  const capturedPlusOutstanding =
    capturedCredits == null || walletBalance == null
      ? undefined
      : capturedCredits + Math.max(walletBalance, 0);
  const userSignups7d = recentSum(analytics?.user_signups, 7);
  const previousUserSignups7d = previousSum(analytics?.user_signups, 7);
  const orgSignups7d = recentSum(analytics?.org_signups, 7);
  const previousOrgSignups7d = previousSum(analytics?.org_signups, 7);
  const creditsSpent7d = recentSum(analytics?.credits_spent_daily, 7);
  const previousCreditsSpent7d = previousSum(analytics?.credits_spent_daily, 7);

  const criticalSignals = [
    {
      label: "Activation rate",
      value: formatPercent(stats?.active_users, stats?.total_users),
      detail:
        stats == null
          ? "Waiting for user stats"
          : `${formatNumber(stats.active_users)} of ${formatNumber(stats.total_users)} users active`,
      to: ROUTES.admin.users,
      testId: "admin-overview-activation-rate",
    },
    {
      label: "Tenant density",
      value: formatDecimal(
        stats && stats.total_organizations > 0
          ? stats.total_users / stats.total_organizations
          : undefined,
      ),
      detail: "average users per organization",
      to: ROUTES.admin.orgs,
      testId: "admin-overview-tenant-density",
    },
    {
      label: "Generation failure rate",
      value: formatPercent(failedGenerations, generationTotal),
      detail: `${formatNumber(failedGenerations)} failed, ${formatNumber(
        pendingGenerations,
      )} pending in 30 days`,
      to: ROUTES.admin.generations,
      testId: "admin-overview-generation-failure-rate",
    },
    {
      label: "Top customer concentration",
      value: formatPercent(topCustomerCredits, capturedCredits),
      detail: "share of captured credits from top customers",
      to: ROUTES.admin.customers,
      testId: "admin-overview-customer-concentration",
    },
  ];

  const operationsItems: MetricPanelItem[] = [
    {
      label: "Overdue privacy requests",
      value: operations?.overdue_privacy_requests,
      detail: "open requests past deadline",
      tone: issueTone(operations?.overdue_privacy_requests),
    },
    {
      label: "Privacy due soon",
      value: operations?.privacy_requests_due_soon,
      detail: "open requests due within 7 days",
      tone: warningTone(operations?.privacy_requests_due_soon),
    },
    {
      label: "Open privacy requests",
      value: operations?.open_privacy_requests,
      detail: "received, verified, or forwarded",
    },
    {
      label: "Stale pending generations",
      value: operations?.stale_pending_generations,
      detail: "pending longer than 2 hours",
      tone: issueTone(operations?.stale_pending_generations),
    },
    {
      label: "Expired credit holds",
      value: operations?.expired_credit_holds,
      detail: "pending reservations past expiry",
      tone: issueTone(operations?.expired_credit_holds),
    },
    {
      label: "Expired invitations",
      value: operations?.expired_invitations,
      detail: "unaccepted invites past expiry",
      tone: warningTone(operations?.expired_invitations),
    },
    {
      label: "Pending invitations",
      value: operations?.pending_invitations,
      detail: "valid invites awaiting acceptance",
    },
  ];

  const securityItems: MetricPanelItem[] = [
    {
      label: "Superusers",
      value: security?.superusers,
      detail: "platform-wide privileged accounts",
      tone:
        security?.superusers == null ? "neutral" : security.superusers > 1 ? "warning" : "success",
    },
    {
      label: "Unverified active users",
      value: security?.unverified_users,
      detail: "active accounts without mailbox proof",
      tone: warningTone(security?.unverified_users),
    },
    {
      label: "Suppressed emails",
      value: security?.email_suppressed_users,
      detail: "hard bounce or spam complaint",
      tone: warningTone(security?.email_suppressed_users),
    },
    {
      label: "Active API keys",
      value: security?.active_api_keys,
      detail: `${formatNumber(security?.api_keys_used_30d)} used in the last 30 days`,
    },
    {
      label: "Unused API keys",
      value: security?.unused_api_keys,
      detail: "active keys that have never been used",
      tone: warningTone(security?.unused_api_keys),
    },
    {
      label: "Stale API keys",
      value: security?.stale_api_keys,
      detail: "no use in 90 days, or never used after 90 days",
      tone: issueTone(security?.stale_api_keys),
    },
  ];

  const commercialItems: MetricPanelItem[] = [
    {
      label: "Billing profiles",
      value: commercial?.organizations_with_billing_account,
      detail: "organizations attached to a payment customer",
    },
    {
      label: "Credit wallets",
      value: commercial?.organizations_with_wallet,
      detail: "organizations that have touched credits",
    },
    {
      label: "Low-balance wallets",
      value: commercial?.low_balance_wallets,
      detail: `1-${formatNumber(commercial?.low_balance_threshold)} credits remaining`,
      tone: warningTone(commercial?.low_balance_wallets),
    },
    {
      label: "Zero-balance wallets",
      value: commercial?.zero_balance_wallets,
      detail: "wallets that cannot start paid work",
      tone: warningTone(commercial?.zero_balance_wallets),
    },
    {
      label: "Negative wallets",
      value: commercial?.negative_wallets,
      detail: "late charges or manual corrections to review",
      tone: issueTone(commercial?.negative_wallets),
    },
  ];

  const recentActionItems: MetricPanelItem[] = recentAdminActions.map((action) => ({
    label: action.label,
    value: action.count,
    detail: "last 7 days",
  }));

  return (
    <div data-testid="admin-overview-page" className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
            Overview
          </h2>
          <p className="mt-1 text-sm text-[var(--slate)]/75">
            Platform health, growth, credit exposure, and support-critical operations.
          </p>
        </div>
        <span className="w-fit rounded-full border border-[var(--mist)] bg-white px-3 py-1 text-xs font-medium text-[var(--slate)]">
          last 30 days
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {cards.map((card) => (
          <StatCard
            key={card.label}
            testId="admin-overview-stat"
            dataId={card.key}
            label={card.label}
            value={card.value}
            detail={card.detail}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <TrendCard
          label="User signups"
          total={sum(analytics?.user_signups)}
          points={analytics?.user_signups}
          context={trendContext(userSignups7d, previousUserSignups7d)}
          testId="admin-overview-signups"
        />
        <TrendCard
          label="Org signups"
          total={sum(analytics?.org_signups)}
          points={analytics?.org_signups}
          context={trendContext(orgSignups7d, previousOrgSignups7d)}
          testId="admin-overview-org-signups"
        />
        <TrendCard
          label="Credits spent"
          total={sum(analytics?.credits_spent_daily)}
          points={analytics?.credits_spent_daily}
          context={trendContext(creditsSpent7d, previousCreditsSpent7d)}
          testId="admin-overview-credits-spent"
        />
      </div>

      <div
        data-testid="admin-overview-critical-signals"
        className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
      >
        {criticalSignals.map((signal) => (
          <SignalCard key={signal.label} {...signal} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {creditCards.map((card) => (
          <Link
            key={card.label}
            to={ROUTES.admin.credits}
            data-testid="admin-overview-credit-stat"
            data-id={card.key}
            className="rounded-xl border border-[var(--mist)] bg-white p-4 transition-colors hover:border-[var(--teal)]/45 hover:bg-[var(--teal)]/5"
          >
            <p className="text-sm text-[var(--slate)]/75">{card.label}</p>
            <p className="mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)] tabular-nums">
              {formatNumber(card.value)}
            </p>
            <p className="mt-2 text-xs text-[var(--slate)]/60">{card.detail}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <BreakdownPanel
          title="Generation health"
          rows={generations}
          emptyLabel="No generation activity in the last 30 days."
          labelFor={statusLabel}
          testId="admin-overview-generations"
        />
        <BreakdownPanel
          title="Generation mix"
          rows={generationKinds}
          emptyLabel="No generation mix data in the last 30 days."
          labelFor={generationKindLabel}
          testId="admin-overview-generation-mix"
        />
        <div
          data-testid="admin-overview-credit-exposure"
          className="rounded-xl border border-[var(--mist)] bg-white p-4"
        >
          <p className="text-sm font-medium text-[var(--ink)]">Credit settlement</p>
          <p className="mt-1 text-xs text-[var(--slate)]/60">
            captured credits against outstanding wallet balance
          </p>
          <p className="mt-4 font-[family-name:var(--font-display)] text-3xl font-semibold text-[var(--ink)] tabular-nums">
            {formatPercent(capturedCredits, capturedPlusOutstanding)}
          </p>
          <div className="mt-4 space-y-2 text-sm text-[var(--slate)]">
            <div className="flex justify-between gap-3">
              <span>Captured</span>
              <span className="font-[family-name:var(--font-mono)] tabular-nums">
                {formatNumber(capturedCredits)}
              </span>
            </div>
            <div className="flex justify-between gap-3">
              <span>Wallet balance</span>
              <span className="font-[family-name:var(--font-mono)] tabular-nums">
                {formatNumber(walletBalance)}
              </span>
            </div>
            <div className="flex justify-between gap-3">
              <span>Pending holds</span>
              <span className="font-[family-name:var(--font-mono)] tabular-nums">
                {formatNumber(analytics?.credit_summary.total_pending_holds)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <TopCustomersPanel customers={topCustomers} capturedCredits={capturedCredits} />
        <div
          data-testid="admin-overview-workflows"
          className="rounded-xl border border-[var(--mist)] bg-white p-4"
        >
          <p className="text-sm font-medium text-[var(--ink)]">Critical admin workflows</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {workflowLinks.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="rounded-lg border border-[var(--mist)] p-3 text-sm transition-colors hover:border-[var(--teal)]/45 hover:bg-[var(--teal)]/5"
              >
                <p className="font-medium text-[var(--ink)]">{item.label}</p>
                <p className="mt-1 text-xs leading-5 text-[var(--slate)]/65">{item.detail}</p>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <MetricPanel
          title="Operations backlog"
          subtitle="queues that need human cleanup"
          items={operationsItems}
          testId="admin-overview-operations-backlog"
          actionTo={ROUTES.admin.privacyRequests}
        />
        <MetricPanel
          title="Security posture"
          subtitle="privilege, verification, and credential hygiene"
          items={securityItems}
          testId="admin-overview-security-posture"
          actionTo={ROUTES.admin.users}
        />
        <MetricPanel
          title="Commercial risk"
          subtitle="billing profile and wallet conditions"
          items={commercialItems}
          testId="admin-overview-commercial-risk"
          actionTo={ROUTES.admin.credits}
        />
        <MetricPanel
          title="Recent admin actions"
          subtitle="mutation audit volume in the last 7 days"
          items={recentActionItems}
          testId="admin-overview-recent-actions"
          actionTo={ROUTES.admin.audit}
          emptyLabel="No admin mutations in the last 7 days."
        />
      </div>

      <p className="text-sm text-[var(--slate)]/75">
        Per-customer credits spent and monthly $ live on{" "}
        <Link
          to={ROUTES.admin.customers}
          data-testid="admin-overview-customers-link"
          className="font-medium text-[var(--teal-deep)] hover:underline"
        >
          Customers
        </Link>
        .
      </p>
    </div>
  );
}
