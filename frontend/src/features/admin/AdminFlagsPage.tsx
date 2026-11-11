import { ErrorAlert } from "../../shared/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { configKeys } from "../config";
import { listFeatureFlags, setFeatureFlag } from "./api";

const FLAG_DESCRIPTIONS: Record<string, string> = {
  community: "Member community: profiles, directory, and direct messaging with a paid tier.",
};

export default function AdminFlagsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<unknown>(null);

  const { data } = useQuery({
    queryKey: ["admin", "flags"],
    queryFn: listFeatureFlags,
  });

  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      setFeatureFlag(key, enabled),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "flags"] });
      // The whole app gates nav/routes on this — flip it everywhere at once.
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
    onError: (err: unknown) => setError(err),
  });

  return (
    <div data-testid="admin-flags-page">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
        Feature flags
      </h2>
      <p className="mt-1 text-sm text-[var(--slate)]/70">
        Runtime module toggles — changes apply immediately, no restart needed.
      </p>
      {!!error && <ErrorAlert error={error} className="mt-2" data-testid="admin-flags-error" />}

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-flags-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Feature</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Last changed</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((flag) => (
              <tr key={flag.key} data-testid="admin-flags-row" data-key={flag.key}>
                <td className="px-4 py-3">
                  <p className="font-medium text-[var(--ink)]">{flag.key}</p>
                  {FLAG_DESCRIPTIONS[flag.key] && (
                    <p className="mt-0.5 text-xs text-[var(--slate)]/65">
                      {FLAG_DESCRIPTIONS[flag.key]}
                    </p>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                      flag.enabled
                        ? "border-[var(--success)] text-[var(--success)]"
                        : "border-[var(--mist)] text-[var(--slate)]/60"
                    }`}
                  >
                    {flag.enabled ? "On" : "Off"}
                  </span>
                </td>
                <td className="px-4 py-3 text-[var(--slate)]/75">
                  {flag.updated_at ? new Date(flag.updated_at).toLocaleString() : "Never (default)"}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    data-testid="admin-flags-toggle-button"
                    onClick={() => toggle.mutate({ key: flag.key, enabled: !flag.enabled })}
                    disabled={toggle.isPending}
                    className={`text-sm font-medium hover:underline disabled:opacity-50 ${
                      flag.enabled ? "text-[var(--danger)]" : "text-[var(--teal-deep)]"
                    }`}
                  >
                    {flag.enabled ? "Turn off" : "Turn on"}
                  </button>
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr data-testid="admin-flags-empty">
                <td colSpan={4} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No feature flags registered.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
