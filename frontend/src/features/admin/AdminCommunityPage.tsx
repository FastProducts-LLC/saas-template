import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Modal, Stamp, ErrorAlert } from "../../shared/ui";
import Pagination from "./Pagination";
import {
  listCommunityMembers,
  setCommunityBan,
  setCommunityHidden,
  type AdminCommunityMember,
} from "./api";

export default function AdminCommunityPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [confirmBan, setConfirmBan] = useState<AdminCommunityMember | null>(null);

  const { data } = useQuery({
    queryKey: ["admin", "community", search, page],
    queryFn: () => listCommunityMembers(search, page),
  });

  const refresh = () => {
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["admin", "community"] });
  };
  const onError = (err: unknown) => setError(err);

  const ban = useMutation({
    mutationFn: ({ userId, banned }: { userId: string; banned: boolean }) =>
      setCommunityBan(userId, banned),
    onSuccess: () => {
      refresh();
      setConfirmBan(null);
    },
    onError,
  });

  const hide = useMutation({
    mutationFn: ({ userId, hidden }: { userId: string; hidden: boolean }) =>
      setCommunityHidden(userId, hidden),
    onSuccess: refresh,
    onError,
  });

  return (
    <div data-testid="admin-community-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
            Community members
          </h2>
          <p className="mt-1 text-sm text-[var(--slate)]/70">
            Includes hidden and banned members. Moderation works even while the community flag is
            off.
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search handle, name, email…"
          data-testid="admin-community-search"
          className="rounded border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--slate)]/50 focus:border-[var(--teal)] focus:outline-none"
        />
      </div>
      {!!error && <ErrorAlert error={error} className="mt-2" data-testid="admin-community-error" />}

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-community-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Member</th>
              <th className="px-4 py-2 font-medium">Email</th>
              <th className="px-4 py-2 font-medium">Tier</th>
              <th className="px-4 py-2 font-medium">State</th>
              <th className="px-4 py-2 font-medium">Joined</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((member) => (
              <tr
                key={member.user_id}
                data-testid="admin-community-row"
                data-id={member.user_id}
                className={member.is_banned ? "opacity-60" : ""}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-[var(--ink)]">{member.display_name}</p>
                  <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--slate)]/70">
                    @{member.handle}
                  </p>
                </td>
                <td className="px-4 py-3 font-[family-name:var(--font-mono)] text-[13px] text-[var(--slate)]">
                  {member.email}
                </td>
                <td className="px-4 py-3">
                  <Stamp
                    className={
                      member.tier === "premium"
                        ? "border-[var(--teal-deep)] text-[var(--teal-deep)]"
                        : "border-[var(--line)] text-[var(--slate)]/70"
                    }
                  >
                    {member.tier}
                  </Stamp>
                </td>
                <td className="px-4 py-3">
                  <span className="flex flex-wrap gap-1">
                    {member.is_banned && (
                      <Stamp className="border-[var(--danger)] text-[var(--danger)]">Banned</Stamp>
                    )}
                    {member.is_hidden && (
                      <Stamp className="border-[var(--info)] text-[var(--info)]">Hidden</Stamp>
                    )}
                    {!member.is_banned && !member.is_hidden && (
                      <Stamp className="border-[var(--success)] text-[var(--success)]">
                        Active
                      </Stamp>
                    )}
                  </span>
                </td>
                <td className="px-4 py-3 font-[family-name:var(--font-mono)] text-[13px] tabular-nums text-[var(--slate)]/75">
                  {new Date(member.joined_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-right text-sm whitespace-nowrap">
                  <button
                    data-testid="admin-community-hide-button"
                    onClick={() =>
                      hide.mutate({ userId: member.user_id, hidden: !member.is_hidden })
                    }
                    disabled={hide.isPending}
                    className="font-medium text-[var(--info)] hover:underline disabled:opacity-50"
                  >
                    {member.is_hidden ? "Unhide" : "Hide"}
                  </button>
                  <button
                    data-testid="admin-community-ban-button"
                    onClick={() =>
                      member.is_banned
                        ? ban.mutate({ userId: member.user_id, banned: false })
                        : setConfirmBan(member)
                    }
                    disabled={ban.isPending}
                    className="ml-3 font-medium text-[var(--danger)] hover:underline disabled:opacity-50"
                  >
                    {member.is_banned ? "Unban" : "Ban"}
                  </button>
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr data-testid="admin-community-empty">
                <td colSpan={6} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No community members yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && <Pagination page={data} onPageChange={setPage} />}
      </div>

      <Modal
        open={confirmBan !== null}
        onClose={() => setConfirmBan(null)}
        title={`Ban @${confirmBan?.handle}?`}
      >
        <p className="text-sm text-[var(--slate)]">
          They'll lose access to the entire community — profile, directory, and messaging — until
          unbanned. Their subscription is NOT canceled automatically; do that from Stripe if needed.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            onClick={() => setConfirmBan(null)}
            className="rounded border border-[var(--line)] px-3 py-1.5 text-sm font-medium text-[var(--ink)]"
          >
            Cancel
          </button>
          <button
            data-testid="admin-community-ban-confirm"
            onClick={() => confirmBan && ban.mutate({ userId: confirmBan.user_id, banned: true })}
            disabled={ban.isPending}
            className="rounded bg-[var(--danger)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Ban member
          </button>
        </div>
      </Modal>
    </div>
  );
}
