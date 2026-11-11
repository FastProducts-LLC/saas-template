import { ErrorAlert } from "../../shared/ui";
import { Fragment, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ADMIN_CREDIT_NOTE_MAX_LENGTH } from "../../shared/lib/policy";
import Pagination from "./Pagination";
import { adjustCredits, listWallets } from "./api";

function AdjustForm({ orgId, onDone }: { orgId: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<unknown>(null);

  const adjust = useMutation({
    mutationFn: () => adjustCredits(orgId, Number(amount), description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "credits"] });
      onDone();
    },
    onError: (err: unknown) => setError(err),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    adjust.mutate();
  }

  return (
    <tr data-testid="admin-credits-detail" data-id={orgId} className="bg-[var(--paper)]">
      <td colSpan={5} className="px-8 py-3">
        <form
          onSubmit={onSubmit}
          data-testid="admin-credits-adjust-form"
          className="flex items-center gap-2"
        >
          <input
            type="number"
            required
            data-testid="admin-credits-amount-input"
            placeholder="±credits"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-28 rounded-md border border-[var(--slate)]/25 px-3 py-2 text-sm"
          />
          <input
            type="text"
            required
            maxLength={ADMIN_CREDIT_NOTE_MAX_LENGTH}
            data-testid="admin-credits-description-input"
            placeholder="Reason (recorded in the ledger and audit log)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="flex-1 rounded-md border border-[var(--slate)]/25 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            data-testid="admin-credits-apply-button"
            disabled={adjust.isPending || amount === "" || Number(amount) === 0}
            className="rounded-lg bg-[var(--teal)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--teal-deep)] disabled:opacity-50"
          >
            Apply
          </button>
          <button
            type="button"
            data-testid="admin-credits-cancel-button"
            onClick={onDone}
            className="px-2 text-sm text-[var(--slate)]/75 hover:underline"
          >
            Cancel
          </button>
        </form>
        {!!error && <ErrorAlert error={error} className="mt-2" data-testid="admin-credits-error" />}
      </td>
    </tr>
  );
}

export default function AdminCreditsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [adjustingId, setAdjustingId] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["admin", "credits", search, page],
    queryFn: () => listWallets(search, page),
  });

  return (
    <div data-testid="admin-credits-page">
      <div className="flex items-center justify-between">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
          Credits
        </h2>
        <input
          type="search"
          data-testid="admin-credits-search-input"
          placeholder="Search organization…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-64 rounded-md border border-[var(--slate)]/25 px-3 py-2 text-sm"
        />
      </div>
      <p className="mt-1 text-sm text-[var(--slate)]/75">
        Balances reflect each wallet's last settled state; adjustments settle the wallet (allowance
        & expiries) before applying.
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-credits-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Organization</th>
              <th className="px-4 py-2 font-medium">Balance</th>
              <th className="px-4 py-2 font-medium">Pending holds</th>
              <th className="px-4 py-2 font-medium">Allowance period</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((wallet) => (
              <Fragment key={wallet.organization_id}>
                <tr data-testid="admin-credits-row" data-id={wallet.organization_id}>
                  <td className="px-4 py-3 font-medium text-[var(--ink)]">
                    {wallet.organization_name}
                  </td>
                  <td
                    className={`px-4 py-3 font-medium ${
                      wallet.balance < 0 ? "text-[var(--danger)]" : "text-[var(--slate)]"
                    }`}
                  >
                    {wallet.balance.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-[var(--slate)]">{wallet.pending_holds}</td>
                  <td className="px-4 py-3 text-[var(--slate)]/75">
                    {wallet.allowance_period ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      data-testid="admin-credits-adjust-button"
                      onClick={() =>
                        setAdjustingId(
                          adjustingId === wallet.organization_id ? null : wallet.organization_id,
                        )
                      }
                      className="text-sm text-[var(--teal-deep)] hover:underline"
                    >
                      {adjustingId === wallet.organization_id ? "Close" : "Adjust"}
                    </button>
                  </td>
                </tr>
                {adjustingId === wallet.organization_id && (
                  <AdjustForm orgId={wallet.organization_id} onDone={() => setAdjustingId(null)} />
                )}
              </Fragment>
            ))}
            {data?.items.length === 0 && (
              <tr data-testid="admin-credits-empty">
                <td colSpan={5} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No wallets yet — wallets are created when an org first uses credits.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && <Pagination page={data} onPageChange={setPage} />}
      </div>
    </div>
  );
}
