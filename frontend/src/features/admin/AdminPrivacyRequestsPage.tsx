import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Pagination from "./Pagination";
import {
  closePrivacyRequest,
  forwardPrivacyRequest,
  fulfillPrivacyRequest,
  listPrivacyRequests,
  rejectPrivacyRequest,
  type PrivacyRequest,
  type PrivacyRequestStatus,
  verifyPrivacyRequest,
} from "./privacyApi";

const statusOptions: Array<PrivacyRequestStatus | ""> = [
  "",
  "received",
  "verified",
  "forwarded",
  "fulfilled",
  "closed",
  "rejected",
];

const statusColors: Record<string, string> = {
  received: "border border-[var(--danger)] text-[var(--danger)]",
  verified: "border border-[var(--info)] text-[var(--info)]",
  forwarded: "border border-[var(--info)] text-[var(--info)]",
  fulfilled: "border border-[var(--success)] text-[var(--success)]",
  closed: "bg-[var(--mist)] text-[var(--slate)]",
  rejected: "border border-[var(--danger)] text-[var(--danger)]",
};

export default function AdminPrivacyRequestsPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<PrivacyRequestStatus | "">("received");
  const [selected, setSelected] = useState<PrivacyRequest | null>(null);
  const [providerRef, setProviderRef] = useState("");
  const [notes, setNotes] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "privacy-requests", status, page],
    queryFn: () => listPrivacyRequests(status, page),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "privacy-requests"] });

  const verify = useMutation({
    mutationFn: (id: string) => verifyPrivacyRequest(id),
    onSuccess: (req) => {
      setSelected(req);
      invalidate();
    },
  });
  const forward = useMutation({
    mutationFn: (id: string) => forwardPrivacyRequest(id, providerRef, notes || undefined),
    onSuccess: (req) => {
      setSelected(req);
      setProviderRef("");
      setNotes("");
      invalidate();
    },
  });
  const fulfill = useMutation({
    mutationFn: (id: string) =>
      fulfillPrivacyRequest(id, {
        provider_reference: providerRef || undefined,
        notes: notes || undefined,
        also_forward: Boolean(providerRef),
      }),
    onSuccess: (req) => {
      setSelected(req);
      setProviderRef("");
      setNotes("");
      invalidate();
    },
  });
  const close = useMutation({
    mutationFn: (id: string) => closePrivacyRequest(id, notes || undefined),
    onSuccess: (req) => {
      setSelected(req);
      invalidate();
    },
  });
  const reject = useMutation({
    mutationFn: (id: string) => rejectPrivacyRequest(id, rejectReason),
    onSuccess: (req) => {
      setSelected(req);
      setRejectReason("");
      invalidate();
    },
  });

  return (
    <div data-testid="admin-privacy-page">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
        Privacy requests
      </h2>
      <p className="mt-1 max-w-2xl text-sm text-[var(--slate)]/75">
        Data-subject access / delete / suppress intake (GDPR/CCPA). Fulfillment marks the request
        done and can record an upstream-processor forward — raw intake fields purge after 90 days;
        hashes and status remain for audit.
      </p>

      <div className="mt-4 flex items-center gap-3">
        <label className="text-sm text-[var(--slate)]">
          Status{" "}
          <select
            data-testid="admin-privacy-status-select"
            className="ml-1 rounded border border-[var(--mist)] bg-white px-2 py-1"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as PrivacyRequestStatus | "");
              setPage(1);
            }}
          >
            {statusOptions.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "all"}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
          <table data-testid="admin-privacy-table" className="w-full text-sm">
            <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
              <tr>
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Subject</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--mist)]">
              {isLoading && (
                <tr data-testid="admin-privacy-loading">
                  <td colSpan={4} className="px-4 py-6 text-center text-[var(--slate)]/55">
                    Loading…
                  </td>
                </tr>
              )}
              {data?.items.map((req) => (
                <tr
                  key={req.id}
                  data-testid="admin-privacy-row"
                  data-id={req.id}
                  className={`cursor-pointer hover:bg-[var(--paper)] ${
                    selected?.id === req.id ? "bg-[var(--paper)]" : ""
                  }`}
                  onClick={() => setSelected(req)}
                >
                  <td className="whitespace-nowrap px-4 py-3 text-[var(--slate)]/75">
                    {new Date(req.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-medium text-[var(--ink)]">{req.request_type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        statusColors[req.status] ?? "bg-[var(--mist)]"
                      }`}
                    >
                      {req.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--slate)]">
                    {req.payload_purged_at ? (
                      <span className="text-xs text-[var(--slate)]/55">
                        purged · hash {req.subject_email_hash?.slice(0, 8) ?? "—"}
                      </span>
                    ) : (
                      <>
                        <p>{req.subject_email ?? req.requester_email ?? "—"}</p>
                        <p className="text-xs text-[var(--slate)]/55">
                          {req.subject_phone ?? req.subject_consumer_key ?? ""}
                        </p>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr data-testid="admin-privacy-empty">
                  <td colSpan={4} className="px-4 py-6 text-center text-[var(--slate)]/55">
                    No privacy requests in this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {data && <Pagination page={data} onPageChange={setPage} />}
        </div>

        <div
          data-testid="admin-privacy-detail"
          className="rounded-xl border border-[var(--mist)] bg-white p-5"
        >
          {!selected ? (
            <p className="text-sm text-[var(--slate)]/55">
              Select a request to review and fulfill.
            </p>
          ) : (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-[var(--slate)]/55">Request</p>
                <p className="font-medium text-[var(--ink)]">
                  {selected.request_type} · {selected.status}
                </p>
                <p className="text-xs text-[var(--slate)]/55">{selected.id}</p>
                {selected.deadline_at && (
                  <p className="mt-1 text-xs text-[var(--slate)]">
                    Deadline {new Date(selected.deadline_at).toLocaleDateString()}
                  </p>
                )}
              </div>

              <div className="grid gap-2 rounded-lg bg-[var(--paper)] p-3 text-xs">
                <p>
                  <span className="text-[var(--slate)]/55">Requester:</span>{" "}
                  {selected.requester_email ?? "(purged)"}
                </p>
                <p>
                  <span className="text-[var(--slate)]/55">Subject email:</span>{" "}
                  {selected.subject_email ?? "(purged)"}
                </p>
                <p>
                  <span className="text-[var(--slate)]/55">Subject phone:</span>{" "}
                  {selected.subject_phone ?? "—"}
                </p>
                {selected.provider_reference && (
                  <p>
                    <span className="text-[var(--slate)]/55">Provider ref:</span>{" "}
                    {selected.provider_reference}
                  </p>
                )}
                {selected.admin_notes && (
                  <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-[var(--slate)]">
                    {selected.admin_notes}
                  </pre>
                )}
              </div>

              <div className="space-y-2">
                <input
                  data-testid="admin-privacy-provider-ref-input"
                  className="w-full rounded border border-[var(--mist)] px-3 py-2"
                  placeholder="Provider ticket / reference"
                  value={providerRef}
                  onChange={(e) => setProviderRef(e.target.value)}
                />
                <textarea
                  data-testid="admin-privacy-notes-input"
                  className="w-full rounded border border-[var(--mist)] px-3 py-2"
                  placeholder="Ops notes"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <input
                  data-testid="admin-privacy-reject-reason-input"
                  className="w-full rounded border border-[var(--mist)] px-3 py-2"
                  placeholder="Rejection reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  data-testid="admin-privacy-verify-button"
                  className="rounded bg-[var(--teal)] px-3 py-1.5 text-white disabled:opacity-40"
                  disabled={selected.status !== "received" || verify.isPending}
                  onClick={() => verify.mutate(selected.id)}
                >
                  Verify
                </button>
                <button
                  type="button"
                  data-testid="admin-privacy-fulfill-button"
                  className="rounded bg-[var(--ink)] px-3 py-1.5 text-white disabled:opacity-40"
                  disabled={
                    !["received", "verified", "forwarded"].includes(selected.status) ||
                    fulfill.isPending
                  }
                  onClick={() => fulfill.mutate(selected.id)}
                >
                  Fulfill
                </button>
                <button
                  type="button"
                  data-testid="admin-privacy-forward-button"
                  className="rounded border border-[var(--mist)] px-3 py-1.5 disabled:opacity-40"
                  disabled={!providerRef || forward.isPending}
                  onClick={() => forward.mutate(selected.id)}
                >
                  Forward only
                </button>
                <button
                  type="button"
                  data-testid="admin-privacy-close-button"
                  className="rounded border border-[var(--mist)] px-3 py-1.5 disabled:opacity-40"
                  disabled={
                    !["fulfilled", "forwarded", "rejected"].includes(selected.status) ||
                    close.isPending
                  }
                  onClick={() => close.mutate(selected.id)}
                >
                  Close
                </button>
                <button
                  type="button"
                  data-testid="admin-privacy-reject-button"
                  className="rounded border border-[var(--danger)]/30 px-3 py-1.5 text-[var(--danger)] disabled:opacity-40"
                  disabled={!rejectReason || reject.isPending}
                  onClick={() => reject.mutate(selected.id)}
                >
                  Reject
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
