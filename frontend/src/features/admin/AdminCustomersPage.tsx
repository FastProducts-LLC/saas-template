import { ErrorAlert } from "../../shared/ui";
import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AdminCustomerUsage } from "./api";
import Pagination from "./Pagination";
import { listCustomers, mergeOrgs } from "./api";

type SortKey = "joined" | "credits";

interface DomainGroup {
  domain: string;
  rows: AdminCustomerUsage[];
}

function emailDomain(email: string | null): string {
  if (!email) return "";
  return email.split("@")[1]?.toLowerCase() ?? "";
}

function groupByDomain(rows: AdminCustomerUsage[]): DomainGroup[] {
  const map = new Map<string, AdminCustomerUsage[]>();
  for (const row of rows) {
    const d = emailDomain(row.owner_email);
    const key = d || `__solo_${row.organization_id}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(row);
  }
  const groups: DomainGroup[] = [];
  for (const [domain, items] of map) {
    if (domain.startsWith("__solo_") || items.length === 1) {
      groups.push({ domain: "", rows: items });
    } else {
      items.sort((a, b) => b.member_count - a.member_count);
      groups.push({ domain, rows: items });
    }
  }
  groups.sort((a, b) => {
    if (a.domain && !b.domain) return -1;
    if (!a.domain && b.domain) return 1;
    return b.rows.length - a.rows.length;
  });
  return groups;
}

function SortHeader({
  label,
  sortKey,
  active,
  onClick,
}: {
  label: string;
  sortKey: SortKey;
  active: boolean;
  onClick: (k: SortKey) => void;
}) {
  return (
    <th
      className="cursor-pointer select-none px-4 py-2 font-medium hover:text-[var(--ink)]"
      onClick={() => onClick(sortKey)}
    >
      {label}
      {active && <span className="ml-1 text-[var(--teal-deep)]">{"▼"}</span>}
    </th>
  );
}

function MergeDialog({
  group,
  onClose,
  onMerge,
  isPending,
}: {
  group: DomainGroup;
  onClose: () => void;
  onMerge: (targetId: string, sourceIds: string[]) => void;
  isPending: boolean;
}) {
  const [targetId, setTargetId] = useState(group.rows[0].organization_id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--ink)]/45 px-4 backdrop-blur-[2px]">
      <div
        data-testid="admin-customers-merge-modal"
        className="w-full max-w-md rounded-lg border border-[var(--line)] bg-white p-6"
      >
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold text-[var(--ink)]">
          Merge @{group.domain} organizations
        </h3>
        <p className="mt-2 text-sm text-[var(--slate)]">
          All members, credits, and usage history will be moved into the selected organization. The
          rest will be deleted.
        </p>

        <fieldset className="mt-4 space-y-2">
          <legend className="text-sm font-medium text-[var(--ink)]">Keep this organization:</legend>
          {group.rows.map((row) => (
            <label
              key={row.organization_id}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                targetId === row.organization_id
                  ? "border-[var(--teal)] bg-[var(--teal)]/5"
                  : "border-[var(--mist)]"
              }`}
            >
              <input
                type="radio"
                name="target"
                data-testid="admin-customers-merge-target-radio"
                data-id={row.organization_id}
                value={row.organization_id}
                checked={targetId === row.organization_id}
                onChange={() => setTargetId(row.organization_id)}
                className="accent-[var(--teal)]"
              />
              <div>
                <p className="font-medium text-[var(--ink)]">
                  {row.organization_name}{" "}
                  <span className="font-normal text-[var(--slate)]/75">
                    ({row.organization_slug})
                  </span>
                </p>
                <p className="text-[var(--slate)]/75">
                  {row.owner_name ?? "—"} · {row.member_count} member
                  {row.member_count !== 1 && "s"} · {row.credits_spent.toLocaleString()} credits
                </p>
              </div>
            </label>
          ))}
        </fieldset>

        <div className="mt-5 flex justify-end gap-3">
          <button
            data-testid="admin-customers-merge-cancel-button"
            onClick={onClose}
            disabled={isPending}
            className="rounded-md px-4 py-2 text-sm text-[var(--slate)] hover:bg-[var(--paper)] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            data-testid="admin-customers-merge-confirm"
            onClick={() => {
              const sourceIds = group.rows
                .filter((r) => r.organization_id !== targetId)
                .map((r) => r.organization_id);
              onMerge(targetId, sourceIds);
            }}
            disabled={isPending}
            className="rounded-md bg-[var(--teal)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--teal-deep)] disabled:opacity-50"
          >
            {isPending ? "Merging…" : `Merge ${group.rows.length - 1} into 1`}
          </button>
        </div>
      </div>
    </div>
  );
}

function CustomerRow({ row, indent }: { row: AdminCustomerUsage; indent?: boolean }) {
  return (
    <tr
      data-testid="admin-customers-row"
      data-id={row.organization_id}
      className={row.suspended_at ? "opacity-60" : ""}
    >
      <td className={`py-3 ${indent ? "pl-10 pr-4" : "px-4"}`}>
        <p className="font-medium text-[var(--ink)]">
          {row.organization_name}
          {row.suspended_at && (
            <span className="ml-2 rounded-full border border-[var(--danger)] px-2 py-0.5 text-xs text-[var(--danger)]">
              suspended
            </span>
          )}
        </p>
        <p className="text-xs text-[var(--slate)]/60">{row.organization_slug}</p>
      </td>
      <td className="px-4 py-3">
        {row.owner_email ? (
          <>
            <p className="text-[var(--ink)]">{row.owner_name ?? "—"}</p>
            <p className="text-xs text-[var(--slate)]/75">{row.owner_email}</p>
          </>
        ) : (
          <span className="text-[var(--slate)]/55">—</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-[var(--slate)]">
        {new Date(row.created_at).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })}
      </td>
      <td className="px-4 py-3 text-[var(--slate)]">{row.member_count}</td>
      <td className="px-4 py-3 text-[var(--slate)]">{row.credits_spent.toLocaleString()}</td>
      <td className="px-4 py-3 text-[var(--slate)]">
        $
        {(row.dollars_spent_cents / 100).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}
      </td>
      <td
        className={`px-4 py-3 ${
          row.credit_balance != null && row.credit_balance < 0
            ? "text-[var(--danger)]"
            : "text-[var(--slate)]"
        }`}
      >
        {row.credit_balance != null ? row.credit_balance.toLocaleString() : "—"}
      </td>
      <td
        className={`px-4 py-3 ${
          row.dollar_balance_cents != null && row.dollar_balance_cents < 0
            ? "text-[var(--danger)]"
            : "text-[var(--slate)]"
        }`}
      >
        {row.dollar_balance_cents != null
          ? `$${(row.dollar_balance_cents / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          : "—"}
      </td>
    </tr>
  );
}

export default function AdminCustomersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortKey>("joined");
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());
  const [mergeGroup, setMergeGroup] = useState<DomainGroup | null>(null);
  const [error, setError] = useState<unknown>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "customers", search, page, sort],
    queryFn: () => listCustomers(search, page, sort),
  });

  const groups = useMemo(() => groupByDomain(data?.items ?? []), [data?.items]);

  const merge = useMutation({
    mutationFn: ({ targetId, sourceIds }: { targetId: string; sourceIds: string[] }) =>
      mergeOrgs(targetId, sourceIds),
    onSuccess: () => {
      setError(null);
      setMergeGroup(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "customers"] });
    },
    onError: (err: unknown) => setError(err),
  });

  const toggleDomain = (domain: string) => {
    setExpandedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  };

  const handleSort = (key: SortKey) => {
    setSort(key);
    setPage(1);
  };

  return (
    <div data-testid="admin-customers-page">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
            Customers
          </h2>
          <p className="mt-1 text-sm text-[var(--slate)]/75">
            Who signed up and how many credits they spent.
          </p>
        </div>
        <input
          type="search"
          data-testid="admin-customers-search-input"
          placeholder="Search org or owner email…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-64 shrink-0 rounded-md border border-[var(--slate)]/25 px-3 py-2 text-sm"
        />
      </div>
      {!!error && <ErrorAlert error={error} className="mt-2" data-testid="admin-customers-error" />}

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-customers-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Organization</th>
              <th className="px-4 py-2 font-medium">Owner</th>
              <SortHeader
                label="Joined"
                sortKey="joined"
                active={sort === "joined"}
                onClick={handleSort}
              />
              <th className="px-4 py-2 font-medium">Members</th>
              <SortHeader
                label="Credits spent"
                sortKey="credits"
                active={sort === "credits"}
                onClick={handleSort}
              />
              <th className="px-4 py-2 font-medium">$ Spent</th>
              <th className="px-4 py-2 font-medium">Balance</th>
              <th className="px-4 py-2 font-medium">$ Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {groups.map((group) => {
              if (!group.domain) {
                return group.rows.map((row) => <CustomerRow key={row.organization_id} row={row} />);
              }

              const expanded = expandedDomains.has(group.domain);
              const totalMembers = group.rows.reduce((s, r) => s + r.member_count, 0);
              const totalCredits = group.rows.reduce((s, r) => s + r.credits_spent, 0);

              return (
                <Fragment key={group.domain}>
                  <tr
                    data-testid="admin-customers-domain-row"
                    data-id={group.domain}
                    className="bg-[var(--paper)]/60"
                  >
                    <td className="px-4 py-2.5" colSpan={3}>
                      <button
                        data-testid="admin-customers-domain-toggle-button"
                        onClick={() => toggleDomain(group.domain)}
                        className="flex items-center gap-2 text-sm font-medium text-[var(--ink)]"
                      >
                        <span
                          className="inline-block text-[10px] text-[var(--slate)]/60 transition-transform"
                          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
                        >
                          &#9654;
                        </span>
                        @{group.domain}
                        <span className="rounded-full border border-[var(--danger)] px-2 py-0.5 text-xs font-medium text-[var(--danger)]">
                          {group.rows.length} orgs — should merge
                        </span>
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-[var(--slate)]">{totalMembers}</td>
                    <td className="px-4 py-2.5 text-[var(--slate)]">
                      {totalCredits.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5" colSpan={2} />
                    <td className="px-4 py-2.5 text-right">
                      <button
                        data-testid="admin-customers-merge-button"
                        onClick={() => setMergeGroup(group)}
                        className="rounded-md border border-[var(--teal)]/30 px-3 py-1 text-xs font-medium text-[var(--teal-deep)] hover:bg-[var(--teal)]/5"
                      >
                        Merge
                      </button>
                    </td>
                  </tr>
                  {expanded &&
                    group.rows.map((row) => (
                      <CustomerRow key={row.organization_id} row={row} indent />
                    ))}
                </Fragment>
              );
            })}
            {isLoading && (
              <tr data-testid="admin-customers-loading">
                <td colSpan={8} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && data?.items.length === 0 && (
              <tr data-testid="admin-customers-empty">
                <td colSpan={8} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No organizations yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && <Pagination page={data} onPageChange={setPage} />}
      </div>

      {mergeGroup && (
        <MergeDialog
          group={mergeGroup}
          onClose={() => setMergeGroup(null)}
          onMerge={(targetId, sourceIds) => merge.mutate({ targetId, sourceIds })}
          isPending={merge.isPending}
        />
      )}
    </div>
  );
}
