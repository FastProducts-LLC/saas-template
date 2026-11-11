import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Pagination from "./Pagination";
import { listGenerations, type GenerationKind, type GenerationStatus } from "./api";

const statusColors: Record<GenerationStatus, string> = {
  pending: "border border-[var(--info)] text-[var(--info)]",
  succeeded: "border border-[var(--success)] text-[var(--success)]",
  failed: "border border-[var(--danger)] text-[var(--danger)]",
  canceled: "border border-[var(--slate)]/40 text-[var(--slate)]",
};

const kindLabels: Record<GenerationKind, string> = {
  image_nano_banana: "Image (Nano Banana)",
  image_gpt: "Image (GPT)",
  video_veo: "Video (VEO)",
  llm_call: "LLM call",
};

export default function AdminGenerationsPage() {
  const [status, setStatus] = useState<GenerationStatus | "">("");
  const [kind, setKind] = useState<GenerationKind | "">("");
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["admin", "generations", status, kind, page],
    queryFn: () => listGenerations(status, kind, page),
  });

  return (
    <div data-testid="admin-generations-page">
      <div className="flex items-center justify-between">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
          Generations
        </h2>
        <div className="flex gap-2">
          <select
            data-testid="admin-generations-status-select"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as GenerationStatus | "");
              setPage(1);
            }}
            className="rounded-md border border-[var(--slate)]/25 px-2 py-2 text-sm"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="canceled">Canceled</option>
          </select>
          <select
            data-testid="admin-generations-kind-select"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as GenerationKind | "");
              setPage(1);
            }}
            className="rounded-md border border-[var(--slate)]/25 px-2 py-2 text-sm"
          >
            <option value="">All kinds</option>
            <option value="image_nano_banana">Image (Nano Banana)</option>
            <option value="image_gpt">Image (GPT)</option>
            <option value="video_veo">Video (VEO)</option>
          </select>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-generations-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Organization</th>
              <th className="px-4 py-2 font-medium">Kind</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Credits</th>
              <th className="px-4 py-2 font-medium">Created</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((gen) => (
              <Fragment key={gen.id}>
                <tr data-testid="admin-generations-row" data-id={gen.id}>
                  <td className="px-4 py-3 font-medium text-[var(--ink)]">
                    {gen.organization_name}
                  </td>
                  <td className="px-4 py-3 text-[var(--slate)]">
                    {kindLabels[gen.kind] ?? gen.kind}
                    <p className="text-xs text-[var(--slate)]/55">{gen.model}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${statusColors[gen.status]}`}
                    >
                      {gen.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--slate)]">{gen.credits_cost}</td>
                  <td className="px-4 py-3 text-[var(--slate)]/75">
                    {new Date(gen.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      data-testid="admin-generations-details-button"
                      onClick={() => setExpandedId(expandedId === gen.id ? null : gen.id)}
                      className="text-sm text-[var(--teal-deep)] hover:underline"
                    >
                      {expandedId === gen.id ? "Hide" : "Details"}
                    </button>
                  </td>
                </tr>
                {expandedId === gen.id && (
                  <tr
                    data-testid="admin-generations-detail"
                    data-id={gen.id}
                    className="bg-[var(--paper)]"
                  >
                    <td colSpan={6} className="px-8 py-3 text-sm">
                      <p className="font-medium text-[var(--slate)]">Prompt</p>
                      <p className="mt-1 whitespace-pre-wrap text-[var(--slate)]">{gen.prompt}</p>
                      {gen.error && (
                        <>
                          <p className="mt-3 font-medium text-[var(--danger)]">Error</p>
                          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-[var(--danger)]">
                            {gen.error}
                          </pre>
                        </>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {data?.items.length === 0 && (
              <tr data-testid="admin-generations-empty">
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No generations found.
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
