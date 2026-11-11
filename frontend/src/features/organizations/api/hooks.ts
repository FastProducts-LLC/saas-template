import { entitlementKeys } from "../../entitlements";
// Domain hooks: components talk to these, never to endpoints or queryClient.
// Mutation hooks own cache invalidation; returning the invalidate promise from
// onSuccess makes TanStack Query await it before per-mutate callbacks run, so
// navigation in components always sees fresh data.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";
import * as endpoints from "./endpoints";
import { orgKeys } from "./keys";
import type { Role } from "../model/types";

export function useOrgs() {
  return useQuery({ queryKey: orgKeys.all, queryFn: endpoints.listOrgs });
}

export function useMembers(orgId: string) {
  return useQuery({
    queryKey: orgKeys.members(orgId),
    queryFn: () => endpoints.listMembers(orgId),
  });
}

export function useInvitations(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: orgKeys.invitations(orgId),
    queryFn: () => endpoints.listInvitations(orgId),
    enabled,
  });
}

/** Shared invalidation for every membership-changing mutation. `onDone`
 *  is the analytics success point (fires once, after the server confirmed). */
function useMembershipMutation<TVars, TData>(
  orgId: string,
  mutationFn: (vars: TVars) => Promise<TData>,
  onDone?: (vars: TVars) => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (_data, vars) => {
      onDone?.(vars);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: entitlementKeys.org(orgId) }),
        queryClient.invalidateQueries({ queryKey: orgKeys.members(orgId) }),
        queryClient.invalidateQueries({ queryKey: orgKeys.invitations(orgId) }),
      ]);
    },
  });
}

export const useInviteMember = (orgId: string) =>
  useMembershipMutation(
    orgId,
    (vars: { email: string; role: Role }) =>
      endpoints.createInvitation(orgId, vars.email, vars.role),
    // The role only — never the invitee's email.
    (vars) => track(EVENTS.invite_sent, { role: vars.role }),
  );

export const useChangeMemberRole = (orgId: string) =>
  useMembershipMutation(orgId, (vars: { membershipId: string; role: Role }) =>
    endpoints.changeMemberRole(orgId, vars.membershipId, vars.role),
  );

export const useRemoveMember = (orgId: string) =>
  useMembershipMutation(orgId, (membershipId: string) =>
    endpoints.removeMember(orgId, membershipId),
  );

export const useRevokeInvitation = (orgId: string) =>
  useMembershipMutation(orgId, (invitationId: string) =>
    endpoints.revokeInvitation(orgId, invitationId),
  );

/** Org list mutation with awaited org-list invalidation. `onDone` is the
 *  analytics success point. */
function useOrgMutation<TVars, TData>(
  mutationFn: (vars: TVars) => Promise<TData>,
  onDone?: () => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      onDone?.();
      return queryClient.invalidateQueries({ queryKey: orgKeys.all });
    },
  });
}

export const useCreateOrg = () =>
  useOrgMutation(
    (payload: { name: string; intended_use: string }) => endpoints.createOrg(payload),
    () => track(EVENTS.org_created),
  );

export const useRenameOrg = () =>
  useOrgMutation(
    (vars: { orgId: string; name: string }) => endpoints.renameOrg(vars.orgId, vars.name),
    () => track(EVENTS.settings_updated, { section: "org_name" }),
  );

export const useDeleteOrg = () => useOrgMutation(endpoints.deleteOrg);

export const useSetOrgDomain = () =>
  useOrgMutation(
    (vars: { orgId: string; domain: string | null }) =>
      endpoints.setOrgDomain(vars.orgId, vars.domain),
    () => track(EVENTS.settings_updated, { section: "org_domain" }),
  );

export const useAcceptInvitation = () =>
  useOrgMutation(endpoints.acceptInvitation, () => track(EVENTS.invite_accepted));
