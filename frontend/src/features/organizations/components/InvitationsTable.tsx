import { Stamp, ErrorAlert } from "../../../shared/ui";
import { useRevokeInvitation } from "../api/hooks";
import type { Invitation } from "../model/types";

export default function InvitationsTable({
  orgId,
  invitations,
}: {
  orgId: string;
  invitations: Invitation[];
}) {
  const revoke = useRevokeInvitation(orgId);

  return (
    <>
      {revoke.error && (
        <ErrorAlert error={revoke.error} className="mt-2" data-testid="invitations-error" />
      )}
      <div className="mt-3 overflow-hidden rounded border border-[var(--line)] bg-white">
        <table data-testid="invitations-table" className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--mist)] font-[family-name:var(--font-mono)]">
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-normal text-[var(--slate)]">
                Email
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-normal text-[var(--slate)]">
                Role
              </th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {invitations.map((inv, idx) => (
              <tr
                key={inv.id}
                data-testid="invitations-row"
                data-id={inv.id}
                className="gd-row-in h-10 border-t border-[var(--line)] transition-colors hover:bg-[var(--paper)]"
                style={{ "--i": idx } as React.CSSProperties}
              >
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[var(--mist)] text-xs font-semibold text-[var(--ink)]">
                      {inv.email.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-sm text-[var(--ink)]">{inv.email}</span>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <Stamp className="border-[var(--line)] text-[var(--slate)]">{inv.role}</Stamp>
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    data-testid="invitations-revoke-button"
                    onClick={() => revoke.mutate(inv.id)}
                    className="px-2 py-1 text-xs font-medium text-[var(--danger)] transition-colors hover:underline"
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
