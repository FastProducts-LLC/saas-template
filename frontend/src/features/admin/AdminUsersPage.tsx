import { ErrorAlert } from "../../shared/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ROUTES } from "../../shared/lib/routes";
import { useAuth } from "../auth";
import Pagination from "./Pagination";
import {
  deactivateUser,
  impersonateUser,
  listUsers,
  reactivateUser,
  signOutUserEverywhere,
} from "./api";

export default function AdminUsersPage() {
  const { user: me, startImpersonation } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const onError = (err: unknown) => setError(err);

  const { data } = useQuery({
    queryKey: ["admin", "users", search, page],
    queryFn: () => listUsers(search, page),
  });

  const setActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      active ? reactivateUser(id) : deactivateUser(id),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
    onError,
  });

  const signOut = useMutation({
    mutationFn: (id: string) => signOutUserEverywhere(id),
    onSuccess: () => setError(null),
    onError,
  });

  const impersonate = useMutation({
    mutationFn: async (id: string) => {
      const grant = await impersonateUser(id);
      await startImpersonation(grant.access_token);
    },
    onSuccess: () => navigate(ROUTES.dashboard),
    onError,
  });

  return (
    <div data-testid="admin-users-page">
      <div className="flex items-center justify-between">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
          Users
        </h2>
        <input
          type="search"
          data-testid="admin-users-search-input"
          placeholder="Search name or email…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-64 rounded-md border border-[var(--slate)]/25 px-3 py-2 text-sm"
        />
      </div>
      {!!error && <ErrorAlert error={error} className="mt-2" data-testid="admin-users-error" />}

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-users-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">User</th>
              <th className="px-4 py-2 font-medium">Orgs</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Joined</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {data?.items.map((u) => (
              <tr
                key={u.id}
                data-testid="admin-users-row"
                data-id={u.id}
                className={u.is_active ? "" : "opacity-60"}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-[var(--ink)]">
                    {u.name}{" "}
                    {u.id === me?.id && <span className="text-[var(--slate)]/55">(you)</span>}
                    {u.is_superuser && (
                      <span className="ml-1 rounded-full border border-[var(--danger)] px-2 py-0.5 text-xs font-medium text-[var(--danger)]">
                        superuser
                      </span>
                    )}
                  </p>
                  <p className="text-[var(--slate)]/75">{u.email}</p>
                </td>
                <td className="px-4 py-3 text-[var(--slate)]">{u.organization_count}</td>
                <td className="px-4 py-3">
                  {u.is_active ? (
                    <span className="rounded-full border border-[var(--success)] px-2 py-0.5 text-xs text-[var(--success)]">
                      active
                    </span>
                  ) : (
                    <span className="rounded-full border border-[var(--danger)] px-2 py-0.5 text-xs text-[var(--danger)]">
                      deactivated
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-[var(--slate)]/75">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="space-x-3 whitespace-nowrap px-4 py-3 text-right">
                  {!u.is_superuser && u.is_active && (
                    <button
                      data-testid="admin-users-impersonate-button"
                      onClick={() => impersonate.mutate(u.id)}
                      disabled={impersonate.isPending}
                      className="text-sm text-[var(--info)] hover:underline disabled:opacity-50"
                    >
                      Impersonate
                    </button>
                  )}
                  {u.id !== me?.id && (
                    <>
                      <button
                        data-testid="admin-users-signout-everywhere-button"
                        onClick={() => signOut.mutate(u.id)}
                        disabled={signOut.isPending}
                        className="text-sm text-[var(--danger)] hover:underline disabled:opacity-50"
                        title="Revoke every session for this user"
                      >
                        Sign out everywhere
                      </button>
                      <button
                        data-testid="admin-users-toggle-active-button"
                        onClick={() => setActive.mutate({ id: u.id, active: !u.is_active })}
                        disabled={setActive.isPending}
                        className={`text-sm hover:underline disabled:opacity-50 ${
                          u.is_active ? "text-[var(--danger)]" : "text-[var(--teal-deep)]"
                        }`}
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr data-testid="admin-users-empty">
                <td colSpan={5} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No users found.
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
