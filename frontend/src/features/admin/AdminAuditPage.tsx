import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Pagination from "./Pagination";
import { listAuditLog } from "./api";

const actionColors: Record<string, string> = {
  "user.deactivate": "border border-[var(--danger)] text-[var(--danger)]",
  "user.reactivate": "border border-[var(--success)] text-[var(--success)]",
  "user.signout_everywhere": "border border-[var(--danger)] text-[var(--danger)]",
  "user.impersonate": "border border-[var(--info)] text-[var(--info)]",
  "org.suspend": "border border-[var(--danger)] text-[var(--danger)]",
  "org.unsuspend": "border border-[var(--success)] text-[var(--success)]",
  "abuse.reinstate": "border border-[var(--success)] text-[var(--success)]",
  "credits.adjust": "border border-[var(--info)] text-[var(--info)]",
  "invitation.revoke": "border border-[var(--danger)] text-[var(--danger)]",
};

export default function AdminAuditPage() {
  const [page, setPage] = useState(1);

  const { data } = useQuery({
    queryKey: ["admin", "audit", page],
    queryFn: () => listAuditLog(page),
  });

  return (
    <div data-testid="admin-audit-page">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
        Audit log
      </h2>
      <p className="mt-1 text-sm text-[var(--slate)]/75">
        Every admin mutation, recorded in the same transaction it ran in. Append-only.
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-audit-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">When</th>
              <th className="px-4 py-2 font-medium">Admin</th>
              <th className="px-4 py-2 font-medium">Action</th>
              <th className="px-4 py-2 font-medium">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((entry) => (
              <tr key={entry.id} data-testid="admin-audit-row" data-id={entry.id}>
                <td className="whitespace-nowrap px-4 py-3 text-[var(--slate)]/75">
                  {new Date(entry.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium text-[var(--ink)]">{entry.actor_name ?? "—"}</p>
                  <p className="text-[var(--slate)]/75">{entry.actor_email ?? "deleted account"}</p>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      actionColors[entry.action] ?? "bg-[var(--mist)] text-[var(--slate)]"
                    }`}
                  >
                    {entry.action}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--slate)]">
                  {Object.entries(entry.meta).map(([key, value]) => (
                    <p key={key} className="text-xs">
                      <span className="text-[var(--slate)]/55">{key}:</span> {String(value)}
                    </p>
                  ))}
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr data-testid="admin-audit-empty">
                <td colSpan={4} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No admin actions recorded yet.
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
