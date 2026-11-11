import { formatMoney } from "../../shared/lib/money";
import { ErrorAlert } from "../../shared/ui";
import { useAdminRevenue } from "./api/entitlements-hooks";
export default function AdminRevenuePage() {
  const { data, isPending, error } = useAdminRevenue();
  if (isPending) return <p role="status">Loading revenue…</p>;
  if (error) return <ErrorAlert error={error} />;
  const counters = [
    ["MRR", formatMoney(data.mrr_cents, { currency: data.currency })],
    ["ARR", formatMoney(data.arr_cents, { currency: data.currency })],
    ["Active", data.active],
    ["Trialing", data.trialing],
    ["Past due", data.past_due],
    ["Canceling", data.canceling],
    ["New in the last 30 days", data.new_last_30d],
    ["Canceled in the last 30 days", data.canceled_last_30d],
  ] as const;
  const empty =
    !data.mrr_cents &&
    !data.arr_cents &&
    !data.active &&
    !data.trialing &&
    !data.past_due &&
    !data.canceling &&
    !data.new_last_30d &&
    !data.canceled_last_30d &&
    data.by_plan.every((row) => !row.count && !row.mrr_cents);
  return (
    <div>
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">Revenue</h1>
      {empty && (
        <p className="mt-4 border-y border-dotted border-[var(--line)] py-4">
          There are no subscriptions yet.
        </p>
      )}
      <dl className="mt-6 grid grid-cols-2 border-t border-[var(--line)] lg:grid-cols-4">
        {counters.map(([label, value]) => (
          <div key={label} className="border-b border-r border-[var(--line)] p-4">
            <dt className="text-sm text-[var(--slate)]">{label}</dt>
            <dd className="font-[family-name:var(--font-mono)] text-4xl tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <h2 className="mt-6 text-xl font-semibold">Per-plan breakdown</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-[var(--mist)]">
            <tr>
              {["Plan", "Interval", "Subscriptions", "MRR"].map((label) => (
                <th key={label} className="px-4 py-2">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-[family-name:var(--font-mono)] text-[13px] tabular-nums">
            {data.by_plan.map((row) => (
              <tr
                key={`${row.plan}-${row.interval}`}
                className="h-10 border-b border-[var(--line)]"
              >
                <td className="px-4">{row.plan}</td>
                <td className="px-4">{row.interval}</td>
                <td className="px-4">{row.count}</td>
                <td className="px-4">{formatMoney(row.mrr_cents, { currency: data.currency })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
