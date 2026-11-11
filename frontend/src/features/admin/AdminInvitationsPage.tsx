import { ErrorAlert } from "../../shared/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Pagination from "./Pagination";
import { listInvitations, revokeInvitation } from "./api";

export default function AdminInvitationsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);

  const { data } = useQuery({
    queryKey: ["admin", "invitations", page],
    queryFn: () => listInvitations(page),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => revokeInvitation(id),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "invitations"] });
    },
    onError: (err: unknown) => setError(err),
  });

  return (
    <div data-testid="admin-invitations-page">
      <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
        Pending invitations
      </h2>
      {!!error && (
        <ErrorAlert error={error} className="mt-2" data-testid="admin-invitations-error" />
      )}

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-invitations-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Invitee</th>
              <th className="px-4 py-2 font-medium">Organization</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">Invited by</th>
              <th className="px-4 py-2 font-medium">Expires</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((inv) => {
              const expired = new Date(inv.expires_at) < new Date();
              return (
                <tr
                  key={inv.id}
                  data-testid="admin-invitations-row"
                  data-id={inv.id}
                  className={expired ? "opacity-60" : ""}
                >
                  <td className="px-4 py-3 font-medium text-[var(--ink)]">{inv.email}</td>
                  <td className="px-4 py-3 text-[var(--slate)]">{inv.organization_name}</td>
                  <td className="px-4 py-3 capitalize text-[var(--slate)]">{inv.role}</td>
                  <td className="px-4 py-3 text-[var(--slate)]/75">
                    {inv.invited_by_email ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-[var(--slate)]/75">
                    {new Date(inv.expires_at).toLocaleDateString()}
                    {expired && <span className="ml-2 text-xs text-[var(--danger)]">expired</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      data-testid="admin-invitations-revoke-button"
                      onClick={() => revoke.mutate(inv.id)}
                      disabled={revoke.isPending}
                      className="text-sm text-[var(--danger)] hover:underline disabled:opacity-50"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              );
            })}
            {data?.items.length === 0 && (
              <tr data-testid="admin-invitations-empty">
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No pending invitations.
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
