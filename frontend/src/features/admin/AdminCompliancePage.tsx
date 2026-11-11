// Soft compliance board for platform admins: curated inventory of controls
// we already ship, gaps, and the software still to build. Not a live scanner
// and not legal advice — update complianceItems.ts when controls change.

import { useMemo, useState } from "react";

import { complianceCategories, countByStatus, type ComplianceStatus } from "./complianceItems";

const statusLabel: Record<ComplianceStatus, string> = {
  in_place: "In place",
  partial: "Partial",
  missing: "Needs software",
};

const statusStyle: Record<ComplianceStatus, string> = {
  in_place: "border border-[var(--success)] text-[var(--success)]",
  partial: "border border-[var(--danger)] text-[var(--danger)]",
  missing: "border border-[var(--danger)] text-[var(--danger)]",
};

const filters: Array<{ id: "all" | ComplianceStatus; label: string }> = [
  { id: "all", label: "All" },
  { id: "in_place", label: "In place" },
  { id: "partial", label: "Partial" },
  { id: "missing", label: "Needs software" },
];

export default function AdminCompliancePage() {
  const [filter, setFilter] = useState<"all" | ComplianceStatus>("all");
  const counts = useMemo(() => countByStatus(), []);

  const categories = useMemo(() => {
    if (filter === "all") return complianceCategories;
    return complianceCategories
      .map((cat) => ({
        ...cat,
        items: cat.items.filter((item) => item.status === filter),
      }))
      .filter((cat) => cat.items.length > 0);
  }, [filter]);

  return (
    <div data-testid="admin-compliance-page">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
        Compliance soft checklist
      </h2>
      <p className="mt-1 max-w-3xl text-sm text-[var(--slate)]/75">
        What the product already covers, what is only partial, and what software we still need to
        build. This is an internal inventory — not certification evidence or legal advice. Edit{" "}
        <code className="rounded bg-[var(--mist)] px-1 text-xs">complianceItems.ts</code> when a
        control ships.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(
          [
            {
              key: "total",
              label: "Controls tracked",
              value: counts.total,
              tone: "text-[var(--ink)]",
            },
            {
              key: "in_place",
              label: "In place",
              value: counts.in_place,
              tone: "text-[var(--success)]",
            },
            {
              key: "partial",
              label: "Partial",
              value: counts.partial,
              tone: "text-[var(--danger)]",
            },
            {
              key: "missing",
              label: "Needs software",
              value: counts.missing,
              tone: "text-[var(--danger)]",
            },
          ] as const
        ).map((card) => (
          <div
            key={card.key}
            data-testid="admin-compliance-stat"
            data-id={card.key}
            className="rounded-xl border border-[var(--mist)] bg-white p-4"
          >
            <p className="text-sm text-[var(--slate)]/75">{card.label}</p>
            <p
              className={`mt-1 font-[family-name:var(--font-display)] text-2xl font-semibold ${card.tone}`}
            >
              {card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            data-testid="admin-compliance-filter-button"
            data-id={f.id}
            onClick={() => setFilter(f.id)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
              filter === f.id
                ? "border-[var(--teal)] bg-[var(--teal)]/10 text-[var(--teal-deep)]"
                : "border-[var(--mist)] bg-white text-[var(--slate)] hover:text-[var(--ink)]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mt-8 space-y-10">
        {categories.map((cat) => (
          <section key={cat.id} data-testid="admin-compliance-category" data-id={cat.id}>
            <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold text-[var(--ink)]">
              {cat.title}
            </h3>
            <p className="mt-1 text-sm text-[var(--slate)]/75">{cat.blurb}</p>

            <div className="mt-4 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
              <table data-testid="admin-compliance-table" className="w-full text-sm">
                <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
                  <tr>
                    <th className="px-4 py-2 font-medium">Control</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="hidden px-4 py-2 font-medium md:table-cell">Framework</th>
                    <th className="px-4 py-2 font-medium">Software</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--mist)]">
                  {cat.items.map((item) => (
                    <tr
                      key={item.id}
                      data-testid="admin-compliance-row"
                      data-id={item.id}
                      className="align-top"
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-[var(--ink)]">{item.title}</p>
                        <p className="mt-1 text-[var(--slate)]/75">{item.summary}</p>
                        <p className="mt-1 text-xs text-[var(--slate)]/55 md:hidden">
                          {item.framework}
                        </p>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyle[item.status]}`}
                        >
                          {statusLabel[item.status]}
                        </span>
                      </td>
                      <td className="hidden px-4 py-3 text-[var(--slate)] md:table-cell">
                        {item.framework}
                      </td>
                      <td className="px-4 py-3 text-[var(--slate)]">
                        <p className="text-xs leading-relaxed">{item.software}</p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>

      {categories.length === 0 && (
        <p
          data-testid="admin-compliance-empty"
          className="mt-8 text-center text-sm text-[var(--slate)]/55"
        >
          No controls match this filter.
        </p>
      )}
    </div>
  );
}
