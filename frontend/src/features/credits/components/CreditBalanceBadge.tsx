import { useWallet } from "../api/hooks";

// Shares the wallet query key, so domain-hook invalidations keep it fresh —
// no polling needed. Lime fill: the live balance is the one accent in the
// sidebar (DESIGN.md "App navigation").
export function CreditBalanceBadge({ orgId }: { orgId: string }) {
  const { data: wallet } = useWallet(orgId);
  if (wallet === undefined) return null;
  return (
    <span
      data-testid="credit-balance"
      className="ml-2 inline-flex rounded-[3px] bg-[var(--lime)] px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] font-medium leading-none tabular-nums text-[var(--ink)]"
    >
      {wallet.balance.toLocaleString()}
    </span>
  );
}
