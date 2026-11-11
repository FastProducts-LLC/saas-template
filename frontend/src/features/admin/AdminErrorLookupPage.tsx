// Support loop: users hit "Copy details" on any error surface and report a
// `CODE · ref` string; pasting it here pulls the captured request context
// (Redis window from shared/policy.toml — see backend app/core/error_handling.py).

import { ErrorAlert } from "../../shared/ui";
import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";

import { ERROR_CONTEXT_RETENTION_DAYS } from "../../shared/lib/policy";
import { lookupError, type ErrorRecord } from "./api";

/** Accepts "ERR_X_001 · a1b2c3d4", "a1b2c3d4", or the full copied blob. */
function parseRef(input: string): string {
  const tail = input.split("·").pop() ?? input;
  return tail.trim().split(/\s+/).pop() ?? "";
}

export default function AdminErrorLookupPage() {
  const [input, setInput] = useState("");
  const [record, setRecord] = useState<ErrorRecord | null>(null);
  const [error, setError] = useState<unknown>(null);

  const lookup = useMutation({
    mutationFn: (ref: string) => lookupError(ref),
    onSuccess: (data) => {
      setRecord(data);
      setError(null);
    },
    onError: (err: unknown) => {
      setRecord(null);
      setError(err);
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const ref = parseRef(input);
    if (ref) lookup.mutate(ref);
  }

  return (
    <div data-testid="admin-errors-page" className="max-w-3xl">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
        Error lookup
      </h2>
      <p className="mt-1 text-sm text-[var(--slate)]/75">
        Paste a user-reported error reference (e.g.{" "}
        <code className="rounded bg-[var(--mist)] px-1">ERR_SRV_001 · a1b2c3d4</code>) to see the
        request context captured at the moment of failure. Records expire after{" "}
        {ERROR_CONTEXT_RETENTION_DAYS} days.
      </p>

      <form onSubmit={onSubmit} data-testid="admin-errors-search-form" className="mt-6 flex gap-2">
        <input
          type="text"
          required
          data-testid="admin-errors-search-input"
          placeholder="CODE · ref  —  or just the ref"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 rounded-md border border-[var(--slate)]/25 px-3 py-2 font-mono text-sm"
        />
        <button
          type="submit"
          data-testid="admin-errors-search-submit"
          disabled={lookup.isPending}
          className="rounded-lg bg-[var(--teal)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--teal-deep)] disabled:opacity-50"
        >
          Look up
        </button>
      </form>

      {!!error && <ErrorAlert error={error} className="mt-4" data-testid="admin-errors-error" />}

      {record && (
        <div
          data-testid="admin-errors-detail"
          className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white"
        >
          <dl className="divide-y divide-[var(--mist)] text-sm">
            {(
              [
                ["Code", record.code],
                ["Reference", record.error_id],
                ["Request", `${record.method} ${record.path}`],
                ["Status", String(record.status)],
                ["Time", record.ts ? new Date(record.ts).toLocaleString() : "—"],
                ["Detail", record.detail],
                ["Query", record.query],
                ["Client", record.client],
                ["User agent", record.user_agent],
              ] as const
            )
              .filter(([, value]) => value)
              .map(([label, value]) => (
                <div key={label} className="flex px-4 py-2.5">
                  <dt className="w-32 shrink-0 text-[var(--slate)]/75">{label}</dt>
                  <dd className="break-all font-mono text-xs text-[var(--ink)]">{value}</dd>
                </div>
              ))}
          </dl>
          {record.traceback && (
            <div
              data-testid="admin-errors-traceback"
              className="border-t border-[var(--mist)] bg-[var(--paper)] px-4 py-3"
            >
              <p className="text-xs font-medium text-[var(--slate)]/75">Traceback</p>
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-[var(--danger)]">
                {record.traceback}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
