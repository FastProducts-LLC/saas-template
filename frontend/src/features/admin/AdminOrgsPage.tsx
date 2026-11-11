import { ErrorAlert } from "../../shared/ui";
import { Link } from "react-router-dom";
import { ROUTES } from "../../shared/lib/routes";
import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AdminOrg } from "./api";
import Pagination from "./Pagination";
import { listOrgMembers, listOrgs, mergeOrgs, suspendOrg, unsuspendOrg } from "./api";

function emailDomain(email: string | null): string {
  if (!email) return "";
  return email.split("@")[1]?.toLowerCase() ?? "";
}

interface DomainGroup {
  domain: string;
  orgs: AdminOrg[];
}

function groupByDomain(orgs: AdminOrg[]): DomainGroup[] {
  const map = new Map<string, AdminOrg[]>();
  for (const org of orgs) {
    const d = emailDomain(org.owner_email);
    const key = d || `__solo_${org.id}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(org);
  }
  const groups: DomainGroup[] = [];
  for (const [domain, items] of map) {
    if (domain.startsWith("__solo_") || items.length === 1) {
      groups.push({ domain: "", orgs: items });
    } else {
      items.sort((a, b) => b.member_count - a.member_count);
      groups.push({ domain, orgs: items });
    }
  }
  groups.sort((a, b) => {
    if (a.domain && !b.domain) return -1;
    if (!a.domain && b.domain) return 1;
    return b.orgs.length - a.orgs.length;
  });
  return groups;
}

function OrgMembersRow({ orgId }: { orgId: string }) {
  const { data: members, isLoading } = useQuery({
    queryKey: ["admin", "org-members", orgId],
    queryFn: () => listOrgMembers(orgId),
  });

  return (
    <tr data-testid="admin-orgs-detail" data-id={orgId} className="bg-[var(--paper)]">
      <td colSpan={5} className="px-8 py-3">
        {isLoading && (
          <p data-testid="admin-orgs-loading" className="text-sm text-[var(--slate)]/55">
            Loading members…
          </p>
        )}
        {members && (
          <table className="w-full text-sm">
            <tbody className="divide-y divide-[var(--mist)]">
              {members.map((m) => (
                <tr key={m.user_id} data-testid="admin-orgs-member-row" data-id={m.user_id}>
                  <td className="py-1.5 text-[var(--ink)]">{m.name}</td>
                  <td className="py-1.5 text-[var(--slate)]/75">{m.email}</td>
                  <td className="py-1.5 capitalize text-[var(--slate)]">{m.role}</td>
                  <td className="py-1.5">
                    {!m.is_active && (
                      <span className="rounded-full border border-[var(--danger)] px-2 py-0.5 text-xs text-[var(--danger)]">
                        deactivated
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </td>
    </tr>
  );
}

function MergeDialog({
  group,
  onClose,
  onMerge,
  isPending,
}: {
  group: DomainGroup;
  onClose: () => void;
  onMerge: (targetId: string, sourceIds: string[]) => void;
  isPending: boolean;
}) {
  const [targetId, setTargetId] = useState(group.orgs[0].id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--ink)]/45 px-4 backdrop-blur-[2px]">
      <div
        data-testid="admin-orgs-merge-modal"
        className="w-full max-w-md rounded-lg border border-[var(--line)] bg-white p-6"
      >
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold text-[var(--ink)]">
          Merge @{group.domain} organizations
        </h3>
        <p className="mt-2 text-sm text-[var(--slate)]">
          All members will be moved into the selected organization. The rest will be deleted.
        </p>

        <fieldset className="mt-4 space-y-2">
          <legend className="text-sm font-medium text-[var(--ink)]">Keep this organization:</legend>
          {group.orgs.map((org) => (
            <label
              key={org.id}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                targetId === org.id
                  ? "border-[var(--teal)] bg-[var(--teal)]/5"
                  : "border-[var(--mist)]"
              }`}
            >
              <input
                type="radio"
                name="target"
                data-testid="admin-orgs-merge-target-radio"
                data-id={org.id}
                value={org.id}
                checked={targetId === org.id}
                onChange={() => setTargetId(org.id)}
                className="accent-[var(--teal)]"
              />
              <div>
                <p className="font-medium text-[var(--ink)]">
                  {org.name}{" "}
                  <span className="font-normal text-[var(--slate)]/75">({org.slug})</span>
                </p>
                <p className="text-[var(--slate)]/75">
                  {org.owner_name ?? "—"} · {org.member_count} member
                  {org.member_count !== 1 && "s"}
                </p>
              </div>
            </label>
          ))}
        </fieldset>

        <div className="mt-5 flex justify-end gap-3">
          <button
            data-testid="admin-orgs-merge-cancel-button"
            onClick={onClose}
            disabled={isPending}
            className="rounded-md px-4 py-2 text-sm text-[var(--slate)] hover:bg-[var(--paper)] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            data-testid="admin-orgs-merge-confirm"
            onClick={() => {
              const sourceIds = group.orgs.filter((o) => o.id !== targetId).map((o) => o.id);
              onMerge(targetId, sourceIds);
            }}
            disabled={isPending}
            className="rounded-md bg-[var(--teal)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--teal-deep)] disabled:opacity-50"
          >
            {isPending ? "Merging…" : `Merge ${group.orgs.length - 1} into 1`}
          </button>
        </div>
      </div>
    </div>
  );
}

function OrgRow({
  org,
  expandedId,
  setExpandedId,
  onSuspendToggle,
  suspendPending,
  indent,
}: {
  org: AdminOrg;
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  onSuspendToggle: (id: string, suspended: boolean) => void;
  suspendPending: boolean;
  indent?: boolean;
}) {
  return (
    <Fragment>
      <tr
        data-testid="admin-orgs-row"
        data-id={org.id}
        className={org.suspended_at ? "opacity-60" : ""}
      >
        <td className={`py-3 ${indent ? "pl-10 pr-4" : "px-4"}`}>
          <p className="font-medium text-[var(--ink)]">
            {org.name}
            {org.suspended_at && (
              <span className="ml-2 rounded-full border border-[var(--danger)] px-2 py-0.5 text-xs font-medium text-[var(--danger)]">
                suspended
              </span>
            )}
          </p>
          <p className="text-[var(--slate)]/75">{org.slug}</p>
        </td>
        <td className="px-4 py-3 text-[var(--slate)]">
          <p>{org.owner_name ?? "—"}</p>
          <p className="text-xs text-[var(--slate)]/60">{org.owner_email ?? ""}</p>
        </td>
        <td className="px-4 py-3 text-[var(--slate)]">{org.member_count}</td>
        <td className="px-4 py-3 text-[var(--slate)]/75">
          {new Date(org.created_at).toLocaleDateString()}
        </td>
        <td className="space-x-3 px-4 py-3 text-right">
          <Link
            className="text-sm text-[var(--teal-deep)] hover:underline"
            to={ROUTES.admin.orgEntitlements(encodeURIComponent(org.id))}
          >
            Entitlements
          </Link>
          <button
            data-testid="admin-orgs-view-members-button"
            onClick={() => setExpandedId(expandedId === org.id ? null : org.id)}
            className="text-sm text-[var(--teal-deep)] hover:underline"
          >
            {expandedId === org.id ? "Hide" : "Members"}
          </button>
          <button
            data-testid="admin-orgs-toggle-suspend-button"
            onClick={() => onSuspendToggle(org.id, !org.suspended_at)}
            disabled={suspendPending}
            className={`text-sm hover:underline disabled:opacity-50 ${
              org.suspended_at ? "text-[var(--teal-deep)]" : "text-[var(--danger)]"
            }`}
          >
            {org.suspended_at ? "Unsuspend" : "Suspend"}
          </button>
        </td>
      </tr>
      {expandedId === org.id && <OrgMembersRow orgId={org.id} />}
    </Fragment>
  );
}

export default function AdminOrgsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());
  const [error, setError] = useState<unknown>(null);
  const [mergeGroup, setMergeGroup] = useState<DomainGroup | null>(null);

  const { data } = useQuery({
    queryKey: ["admin", "orgs", search, page],
    queryFn: () => listOrgs(search, page),
  });

  const groups = useMemo(() => groupByDomain(data?.items ?? []), [data?.items]);

  const setSuspended = useMutation({
    mutationFn: ({ id, suspended }: { id: string; suspended: boolean }) =>
      suspended ? suspendOrg(id) : unsuspendOrg(id),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "orgs"] });
    },
    onError: (err: unknown) => setError(err),
  });

  const merge = useMutation({
    mutationFn: ({ targetId, sourceIds }: { targetId: string; sourceIds: string[] }) =>
      mergeOrgs(targetId, sourceIds),
    onSuccess: () => {
      setError(null);
      setMergeGroup(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "orgs"] });
    },
    onError: (err: unknown) => setError(err),
  });

  const toggleDomain = (domain: string) => {
    setExpandedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  };

  return (
    <div data-testid="admin-orgs-page">
      <div className="flex items-center justify-between">
        <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold text-[var(--ink)]">
          Organizations
        </h2>
        <input
          type="search"
          data-testid="admin-orgs-search-input"
          placeholder="Search name or slug…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-64 rounded-md border border-[var(--slate)]/25 px-3 py-2 text-sm"
        />
      </div>
      {!!error && <ErrorAlert error={error} className="mt-2" data-testid="admin-orgs-error" />}

      <div className="mt-6 overflow-hidden rounded-xl border border-[var(--mist)] bg-white">
        <table data-testid="admin-orgs-table" className="w-full text-sm">
          <thead className="bg-[var(--paper)] text-left text-[var(--slate)]/80">
            <tr>
              <th className="px-4 py-2 font-medium">Organization</th>
              <th className="px-4 py-2 font-medium">Owner</th>
              <th className="px-4 py-2 font-medium">Members</th>
              <th className="px-4 py-2 font-medium">Created</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--mist)]">
            {groups.map((group) => {
              if (!group.domain) {
                return group.orgs.map((org) => (
                  <OrgRow
                    key={org.id}
                    org={org}
                    expandedId={expandedId}
                    setExpandedId={setExpandedId}
                    onSuspendToggle={(id, suspended) => setSuspended.mutate({ id, suspended })}
                    suspendPending={setSuspended.isPending}
                  />
                ));
              }

              const expanded = expandedDomains.has(group.domain);
              const totalMembers = group.orgs.reduce((s, o) => s + o.member_count, 0);

              return (
                <Fragment key={group.domain}>
                  <tr
                    data-testid="admin-orgs-domain-row"
                    data-id={group.domain}
                    className="bg-[var(--paper)]/60"
                  >
                    <td className="px-4 py-2.5" colSpan={2}>
                      <button
                        data-testid="admin-orgs-domain-toggle-button"
                        onClick={() => toggleDomain(group.domain)}
                        className="flex items-center gap-2 text-sm font-medium text-[var(--ink)]"
                      >
                        <span
                          className="inline-block text-[10px] text-[var(--slate)]/60 transition-transform"
                          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
                        >
                          &#9654;
                        </span>
                        @{group.domain}
                        <span className="rounded-full bg-[var(--teal)]/10 px-2 py-0.5 text-xs font-medium text-[var(--teal-deep)]">
                          {group.orgs.length} orgs
                        </span>
                      </button>
                    </td>
                    <td className="px-4 py-2.5 text-[var(--slate)]">{totalMembers}</td>
                    <td className="px-4 py-2.5" />
                    <td className="px-4 py-2.5 text-right">
                      <button
                        data-testid="admin-orgs-merge-button"
                        onClick={() => setMergeGroup(group)}
                        className="rounded-md border border-[var(--teal)]/30 px-3 py-1 text-xs font-medium text-[var(--teal-deep)] hover:bg-[var(--teal)]/5"
                      >
                        Merge
                      </button>
                    </td>
                  </tr>
                  {expanded &&
                    group.orgs.map((org) => (
                      <OrgRow
                        key={org.id}
                        org={org}
                        expandedId={expandedId}
                        setExpandedId={setExpandedId}
                        onSuspendToggle={(id, suspended) => setSuspended.mutate({ id, suspended })}
                        suspendPending={setSuspended.isPending}
                        indent
                      />
                    ))}
                </Fragment>
              );
            })}
            {data?.items.length === 0 && (
              <tr data-testid="admin-orgs-empty">
                <td colSpan={5} className="px-4 py-6 text-center text-[var(--slate)]/55">
                  No organizations found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && <Pagination page={data} onPageChange={setPage} />}
      </div>

      {mergeGroup && (
        <MergeDialog
          group={mergeGroup}
          onClose={() => setMergeGroup(null)}
          onMerge={(targetId, sourceIds) => merge.mutate({ targetId, sourceIds })}
          isPending={merge.isPending}
        />
      )}
    </div>
  );
}
