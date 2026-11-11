import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { formatMoney } from "../../../shared/lib/money";
import creditsArt from "../../../shared/assets/art/feature-credits.webp";
import {
  Alert,
  Button,
  ErrorAlert,
  Meter,
  PageHeader,
  SectionRule,
  Stamp,
} from "../../../shared/ui";
import { Art } from "../../../shared/ui/marketing";
import { isAdmin, useOrg } from "../../organizations";
import {
  HISTORY_PAGE_SIZE,
  HOLD_OUTCOME,
  PackDiscountStamp,
  TYPE_LABELS,
  TYPE_STYLES,
  useBuyCreditPack,
  useCreditHistory,
  useCreditPacks,
  useRefreshCredits,
  useWallet,
} from "../../credits";
import type { CreditPackSpec, CreditTransaction, Wallet } from "../../credits";
import { useBillingAccount, useBillingPortal, useRefreshBilling } from "../api/hooks";
import InvoicesSection from "./InvoicesSection";
import PlanSection from "./PlanSection";
import UsageSection from "./UsageSection";

const LOW_BALANCE_THRESHOLD = 10;

function Amount({ value }: { value: number }) {
  const sign = value > 0 ? "+" : "";
  const color =
    value > 0
      ? "text-[var(--success)]"
      : value < 0
        ? "text-[var(--ink)]"
        : "text-[var(--slate)]/75";
  return (
    <span className={`font-[family-name:var(--font-mono)] font-medium tabular-nums ${color}`}>
      {sign}
      {value.toLocaleString()}
    </span>
  );
}

function HistoryRow({ tx, index }: { tx: CreditTransaction; index: number }) {
  const outcome =
    tx.type === "hold" && tx.reservation_status ? HOLD_OUTCOME[tx.reservation_status] : null;
  return (
    <tr
      data-testid="billing-history-row"
      data-id={tx.id}
      className="gd-row-in h-10 border-t border-[var(--line)] text-[13px]"
      style={{ "--i": index } as CSSProperties}
    >
      <td className="whitespace-nowrap px-4 py-2 font-[family-name:var(--font-mono)] text-[var(--slate)]/75 tabular-nums">
        {new Date(tx.created_at).toLocaleString()}
      </td>
      <td className="px-4 py-2">
        <Stamp className={TYPE_STYLES[tx.type]}>{TYPE_LABELS[tx.type]}</Stamp>
        {outcome && <Stamp className={`ml-1.5 ${outcome.className}`}>{outcome.label}</Stamp>}
      </td>
      <td className="px-4 py-2 font-[family-name:var(--font-mono)] text-[var(--slate)]">
        {tx.description ?? "—"}
        {tx.user_email && <span className="block text-[var(--slate)]/55">{tx.user_email}</span>}
        {!tx.user_email && tx.api_key_name && (
          <span className="block text-[var(--slate)]/55">API key · {tx.api_key_name}</span>
        )}
      </td>
      <td className="px-4 py-2 text-right">
        <Amount value={tx.amount} />
      </td>
      <td className="px-4 py-2 text-right font-[family-name:var(--font-mono)] tabular-nums text-[var(--slate)]/75">
        {tx.balance_after.toLocaleString()}
      </td>
    </tr>
  );
}

function LegendRow({
  swatch,
  label,
  value,
  testId,
}: {
  swatch?: string;
  label: string;
  value: ReactNode;
  testId?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <dt className="flex items-center gap-2 text-[13px] text-[var(--slate)]">
        {swatch && <span aria-hidden className={`h-2 w-2 rounded-[1px] ${swatch}`} />}
        {label}
      </dt>
      <dd
        data-testid={testId}
        className="font-[family-name:var(--font-mono)] text-[13px] tabular-nums text-[var(--ink)]"
      >
        {value}
      </dd>
    </div>
  );
}

// Credit balance panel: the visual half of the billing overview.
function BalancePanel({ wallet, lowBalance }: { wallet: Wallet | undefined; lowBalance: boolean }) {
  const holds = wallet?.pending_holds.length ?? 0;
  return (
    <div
      data-testid="billing-credits"
      className="relative flex flex-col overflow-hidden rounded border border-[var(--sand-line)] bg-[var(--sand)] p-6"
    >
      <Art
        src={creditsArt}
        width={1200}
        height={800}
        priority
        className="absolute -right-10 -top-6 hidden w-[300px] sm:block"
      />
      <div className="relative">
        <p className="font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-[0.08em] text-[var(--slate)]">
          Credit balance
        </p>
        <p
          data-testid="billing-credits-balance"
          className="mt-3 font-[family-name:var(--font-display)] text-[56px] leading-none tabular-nums text-[var(--ink)]"
        >
          {wallet ? wallet.balance.toLocaleString() : "…"}
        </p>
        <p className="mt-2 text-sm text-[var(--slate)]">credits available to spend</p>
        {lowBalance && (
          <p className="mt-1 text-xs font-medium text-[var(--danger)]">
            Running low — top up below.
          </p>
        )}
      </div>

      <div className="relative mt-auto pt-6">
        <Meter
          label={
            wallet
              ? `${wallet.balance.toLocaleString()} available, ${wallet.reserved.toLocaleString()} on hold`
              : "Loading balance"
          }
          segments={[
            { value: wallet?.balance ?? 0, className: "bg-[var(--ink)]" },
            { value: wallet?.reserved ?? 0, className: "bg-[var(--ink)]/30" },
          ]}
        />
        <dl className="mt-3 divide-y divide-[var(--sand-line)]">
          <LegendRow
            swatch="bg-[var(--ink)]"
            label="Available"
            value={wallet ? wallet.balance.toLocaleString() : "…"}
          />
          <LegendRow
            swatch="bg-[var(--ink)]/30"
            label={
              holds > 0 ? `On hold · ${holds} action${holds === 1 ? "" : "s"} running` : "On hold"
            }
            value={wallet ? wallet.reserved.toLocaleString() : "…"}
            testId="billing-credits-reserved"
          />
          {(!wallet || wallet.monthly_allowance > 0) && (
            <LegendRow
              label="Added every month"
              value={wallet ? `+${wallet.monthly_allowance.toLocaleString()}` : "…"}
              testId="billing-credits-allowance"
            />
          )}
        </dl>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-xs text-xs leading-relaxed text-[var(--slate)]">
            Actions hold credits up front and only charge them once the result is delivered.
          </p>
          <a
            href="#top-up"
            className="rounded border border-[var(--ink)]/15 bg-white px-3 py-1.5 text-[13px] font-medium text-[var(--ink)] transition-colors hover:border-[var(--ink)]/40"
          >
            Buy credits ↓
          </a>
        </div>
      </div>
    </div>
  );
}

function PackCard({
  pack,
  admin,
  buying,
  redirecting,
  onBuy,
  highlighted,
  savingsCents,
  maxCredits,
  index,
}: {
  pack: CreditPackSpec;
  admin: boolean;
  buying: boolean;
  redirecting: boolean;
  onBuy: () => void;
  highlighted: boolean;
  savingsCents: number;
  maxCredits: number;
  index: number;
}) {
  return (
    <div
      data-testid="billing-pack"
      data-id={pack.pack}
      className={`gd-stagger-item relative flex flex-col rounded border bg-white p-5 ${
        highlighted ? "border-[var(--ink)]" : "border-[var(--line)]"
      }`}
      style={{ "--i": index + 2 } as CSSProperties}
    >
      <div className="flex min-h-5 flex-wrap items-center gap-2">
        <p className="text-[15px] font-semibold text-[var(--ink)]">{pack.name}</p>
        {highlighted && <Stamp className="border-[var(--ink)] text-[var(--ink)]">Best value</Stamp>}
        <PackDiscountStamp pct={pack.discount_pct} />
      </div>

      <p className="mt-4 font-[family-name:var(--font-display)] text-[36px] leading-none tabular-nums text-[var(--ink)]">
        {formatMoney(pack.price_cents, { fractionDigits: 0 })}
      </p>

      <Meter
        size="sm"
        className="mt-5"
        label={`${pack.credits.toLocaleString()} credits`}
        max={maxCredits}
        segments={[{ value: pack.credits, className: "bg-[var(--ink)]" }]}
      />
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <p className="font-[family-name:var(--font-mono)] text-sm tabular-nums text-[var(--ink)]">
          {pack.credits.toLocaleString()} credits
        </p>
        <p className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--slate)]">
          {formatMoney(pack.unit_price_cents)} each
        </p>
      </div>
      <p className="mt-1 min-h-4 font-[family-name:var(--font-mono)] text-xs tabular-nums text-[var(--success)]">
        {savingsCents > 0 ? `Save ${formatMoney(savingsCents, { fractionDigits: 0 })}` : ""}
      </p>

      <div className="mt-auto pt-5">
        {admin ? (
          pack.purchasable ? (
            <Button
              data-testid="billing-pack-buy-button"
              onClick={onBuy}
              disabled={buying}
              variant={highlighted ? "primary" : "secondary"}
              className="w-full"
            >
              {redirecting ? "Redirecting…" : `Buy ${pack.name}`}
            </Button>
          ) : (
            <p className="flex h-9 items-center justify-center rounded border border-dashed border-[var(--line)] text-xs text-[var(--slate)]">
              Not on sale yet
            </p>
          )
        ) : (
          <p className="flex h-9 items-center justify-center text-xs text-[var(--slate)]">
            Admins can buy credits
          </p>
        )}
      </div>
    </div>
  );
}

export default function BillingPage() {
  const { currentOrg } = useOrg();
  const [params] = useSearchParams();
  const orgId = currentOrg!.id;
  const admin = isAdmin(currentOrg!.role);

  const { data: account } = useBillingAccount(orgId);
  const portal = useBillingPortal(orgId);

  const { data: wallet } = useWallet(orgId);
  const { data: packs = [] } = useCreditPacks();
  const buyPack = useBuyCreditPack(orgId);
  const refreshCredits = useRefreshCredits(orgId);
  const refreshBilling = useRefreshBilling(orgId);
  const { data: history } = useCreditHistory(orgId, 0);
  const [historyPage, setHistoryPage] = useState(0);
  const historyQuery = useCreditHistory(orgId, historyPage);
  const historyData = historyQuery.data ?? history;
  const [activityOpen, setActivityOpen] = useState(false);

  const status = params.get("status");
  const billingBusy = portal.isPending || portal.isSuccess;
  const creditsBusy = buyPack.isPending || buyPack.isSuccess;
  const billingError = portal.error;

  useEffect(() => {
    if (status !== "success" && status !== "canceled") return;
    refreshBilling();
    refreshCredits();
    const timer = setTimeout(() => {
      refreshCredits();
      refreshBilling();
    }, 3000);
    return () => clearTimeout(timer);
  }, [status, refreshCredits, refreshBilling]);

  const totalPages = historyData
    ? Math.max(1, Math.ceil(historyData.total / HISTORY_PAGE_SIZE))
    : 1;

  const lowBalance = wallet !== undefined && wallet.balance <= LOW_BALANCE_THRESHOLD;

  const baseUnitPrice = packs.length > 0 ? Math.max(...packs.map((p) => p.unit_price_cents)) : 0;
  const bestValuePack = packs.reduce<CreditPackSpec | null>(
    (best, p) => (p.discount_pct > 0 && (!best || p.discount_pct > best.discount_pct) ? p : best),
    null,
  );

  const maxCredits = packs.length > 0 ? Math.max(...packs.map((p) => p.credits)) : 0;
  const manageBilling = admin && account?.has_billing_account && (
    <Button
      data-testid="billing-portal-button"
      variant="secondary"
      onClick={() => portal.mutate()}
      disabled={billingBusy}
    >
      {portal.isPending || portal.isSuccess ? "Redirecting…" : "Payment methods & receipts"}
    </Button>
  );

  return (
    <div data-testid="billing-page" className="max-w-[1200px]">
      <PageHeader
        title="Billing"
        description={`The plan, credit balance, and invoices for ${currentOrg!.name}.`}
        actions={manageBilling}
      />

      {status === "success" && (
        <Alert data-testid="billing-success" tone="success" className="mt-6">
          Payment received — changes are applied as soon as Stripe confirms (a few seconds).
        </Alert>
      )}
      {status === "canceled" && (
        <Alert data-testid="billing-canceled" tone="warning" className="mt-6">
          Checkout canceled.
        </Alert>
      )}
      <ErrorAlert error={billingError} className="mt-6" data-testid="billing-error" />
      <ErrorAlert error={buyPack.error} className="mt-6" data-testid="billing-buy-error" />

      <div className="mt-8">
        <PlanSection
          key={orgId}
          orgId={orgId}
          admin={admin}
          aside={<BalancePanel wallet={wallet} lowBalance={lowBalance} />}
        />
      </div>

      {/* ── Top up ── */}
      {packs.length > 0 && (
        <section data-testid="billing-packs" className="mt-12" aria-label="Buy credits">
          <SectionRule id="top-up" index="02" title="Buy credits" />
          <p className="mt-2 text-sm text-[var(--slate)]">
            One-time top-ups on any plan. Purchased credits never expire.
          </p>

          <div
            className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[repeat(var(--pack-cols),minmax(0,1fr))]"
            style={{ "--pack-cols": packs.length } as CSSProperties}
          >
            {packs.map((p, i) => {
              const redirecting =
                (buyPack.isPending || buyPack.isSuccess) && buyPack.variables === p.pack;
              const savingsCents =
                baseUnitPrice > 0 ? p.credits * baseUnitPrice - p.price_cents : 0;
              return (
                <PackCard
                  key={p.pack}
                  pack={p}
                  admin={admin}
                  buying={creditsBusy}
                  redirecting={!!redirecting}
                  onBuy={() => buyPack.mutate(p.pack)}
                  highlighted={bestValuePack?.pack === p.pack}
                  savingsCents={Math.max(0, savingsCents)}
                  maxCredits={maxCredits}
                  index={i}
                />
              );
            })}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded border border-[var(--line)] bg-[var(--paper)] px-5 py-4">
            <div>
              <p className="text-sm font-semibold text-[var(--ink)]">Enterprise</p>
              <p className="mt-0.5 text-[13px] text-[var(--slate)]">
                Volume pricing, invoicing, and custom terms for high-volume teams.
              </p>
            </div>
            <Stamp className="border-[var(--line)] text-[var(--slate)]">Coming soon</Stamp>
          </div>
        </section>
      )}

      {/* ── Usage by member ── */}
      <section className="mt-12" aria-label="Usage by member">
        <SectionRule index="03" title="Usage by member" />
        <UsageSection orgId={orgId} admin={admin} />
      </section>

      {/* ── Activity ── */}
      <section className="mt-12" aria-label="Activity">
        <SectionRule index="04" title="Activity" />

        <div
          data-testid="billing-activity"
          className="mt-3 overflow-hidden rounded border border-[var(--line)] bg-white"
        >
          <button
            data-testid="billing-activity-toggle-button"
            aria-expanded={activityOpen}
            onClick={() => setActivityOpen((o) => !o)}
            className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-[var(--paper)]"
          >
            <h3 className="text-[13px] font-semibold text-[var(--ink)]">
              Credit history
              {historyData && (
                <span className="ml-2 font-[family-name:var(--font-mono)] font-normal tabular-nums text-[var(--slate)]">
                  {historyData.total.toLocaleString()} transaction
                  {historyData.total !== 1 ? "s" : ""}
                </span>
              )}
            </h3>
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--slate)]">
              {activityOpen ? "Hide" : "Show"}
              <svg
                viewBox="0 0 16 16"
                aria-hidden="true"
                className={`h-3 w-3 transition-transform ${activityOpen ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
              >
                <path d="M4 6l4 4 4-4" />
              </svg>
            </span>
          </button>
          {activityOpen && (
            <>
              {historyData && historyData.total > HISTORY_PAGE_SIZE && (
                <div className="flex items-center justify-end border-t border-[var(--line)] px-4 py-1.5">
                  <div className="flex items-center gap-2 text-sm text-[var(--slate)]/75">
                    <button
                      data-testid="billing-history-prev-button"
                      onClick={() => setHistoryPage((p) => Math.max(0, p - 1))}
                      disabled={historyPage === 0}
                      className="rounded border border-[var(--line)] px-2 py-0.5 text-xs hover:bg-[var(--paper)] disabled:opacity-40"
                    >
                      ←
                    </button>
                    <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums">
                      {historyPage + 1} / {totalPages}
                    </span>
                    <button
                      data-testid="billing-history-next-button"
                      onClick={() => setHistoryPage((p) => Math.min(totalPages - 1, p + 1))}
                      disabled={historyPage >= totalPages - 1}
                      className="rounded border border-[var(--line)] px-2 py-0.5 text-xs hover:bg-[var(--paper)] disabled:opacity-40"
                    >
                      →
                    </button>
                  </div>
                </div>
              )}
              <table data-testid="billing-history-table" className="w-full text-left">
                <thead>
                  <tr className="h-10 border-t border-[var(--line)] bg-[var(--mist)] font-[family-name:var(--font-mono)] text-[11px] uppercase tracking-normal text-[var(--slate)]">
                    <th className="px-4 py-2 font-medium">When</th>
                    <th className="px-4 py-2 font-medium">Event</th>
                    <th className="px-4 py-2 font-medium">Details</th>
                    <th className="px-4 py-2 text-right font-medium">Credits</th>
                    <th className="px-4 py-2 text-right font-medium">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {historyData?.items.map((tx, i) => (
                    <HistoryRow key={tx.id} tx={tx} index={i} />
                  ))}
                  {historyData && historyData.items.length === 0 && (
                    <tr
                      data-testid="billing-history-empty"
                      className="border-t border-[var(--line)]"
                    >
                      <td
                        colSpan={5}
                        className="px-4 py-8 text-center text-sm text-[var(--slate)]/55"
                      >
                        No credit activity yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          )}
        </div>
      </section>

      {admin && <InvoicesSection orgId={orgId} enabled={admin} />}
    </div>
  );
}
