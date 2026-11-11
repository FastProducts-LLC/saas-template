import { Stamp, ErrorAlert } from "../../../shared/ui";
import { useChangeMemberRole, useRemoveMember } from "../api/hooks";
import { canEditMemberRole, isAdmin, isOwner } from "../model/permissions";
import type { Member, Role } from "../model/types";

interface MembersTableProps {
  orgId: string;
  members: Member[];
  currentUserId: string | undefined;
  actorRole: Role;
}

function roleStampStyle(role: string) {
  switch (role) {
    case "owner":
      return "border-[var(--teal)] text-[var(--teal-deep)]";
    case "admin":
      return "border-[var(--info)] text-[var(--info)]";
    default:
      return "border-[var(--line)] text-[var(--slate)]";
  }
}

function avatarInitial(name: string | undefined) {
  return (name ?? "?").charAt(0).toUpperCase();
}

export default function MembersTable({
  orgId,
  members,
  currentUserId,
  actorRole,
}: MembersTableProps) {
  const changeRole = useChangeMemberRole(orgId);
  const remove = useRemoveMember(orgId);
  const error = changeRole.error ?? remove.error;

  return (
    <>
      {error && <ErrorAlert error={error} className="mt-2" data-testid="members-error" />}
      <div className="mt-3 overflow-hidden rounded border border-[var(--line)] bg-white">
        <table data-testid="members-table" className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--mist)] font-[family-name:var(--font-mono)]">
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-normal text-[var(--slate)]">
                Member
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-normal text-[var(--slate)]">
                Role
              </th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {members.map((m, idx) => {
              const isSelf = m.user_id === currentUserId;
              return (
                <tr
                  key={m.id}
                  data-testid="members-row"
                  data-id={m.id}
                  className="gd-row-in h-10 border-t border-[var(--line)] transition-colors hover:bg-[var(--paper)]"
                  style={{ "--i": idx } as React.CSSProperties}
                >
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[var(--mist)] text-xs font-semibold text-[var(--ink)]">
                        {avatarInitial(m.name)}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-[var(--ink)]">
                          {m.name} {isSelf && <span className="text-[var(--slate)]/55">(you)</span>}
                        </p>
                        <p className="truncate text-xs text-[var(--slate)]">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    {canEditMemberRole(actorRole, m.role) ? (
                      <select
                        data-testid="members-role-select"
                        value={m.role}
                        onChange={(e) =>
                          changeRole.mutate({ membershipId: m.id, role: e.target.value as Role })
                        }
                        className="rounded border border-[var(--line)] bg-white px-2 py-1 text-xs capitalize focus:border-[var(--teal)] focus:outline-none focus:ring-1 focus:ring-[var(--teal)]"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                        {isOwner(actorRole) && <option value="owner">Owner</option>}
                      </select>
                    ) : (
                      <Stamp className={roleStampStyle(m.role)}>{m.role}</Stamp>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {(isSelf || isAdmin(actorRole)) && (
                      <button
                        data-testid="members-remove-button"
                        onClick={() => remove.mutate(m.id)}
                        className="px-2 py-1 text-xs font-medium text-[var(--danger)] transition-colors hover:underline"
                      >
                        {isSelf ? "Leave" : "Remove"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
