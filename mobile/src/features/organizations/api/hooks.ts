import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { entitlementKeys } from "../../entitlements";
import type { Role } from "../model/types";
import * as endpoints from "./endpoints";
import { orgKeys } from "./keys";

export function useOrgs(enabled = true) {
  return useQuery({ queryKey: orgKeys.all, queryFn: endpoints.listOrgs, enabled });
}

export function useCreateOrg(onSuccess?: (orgId: string) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endpoints.createOrg,
    onSuccess: async (org) => {
      await queryClient.invalidateQueries({ queryKey: orgKeys.all });
      onSuccess?.(org.id);
    },
  });
}

export function useMembers(orgId: string | undefined) {
  return useQuery({
    queryKey: orgKeys.members(orgId ?? ""),
    queryFn: () => endpoints.listMembers(orgId!),
    enabled: !!orgId,
  });
}

export function useInvitations(orgId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: orgKeys.invitations(orgId ?? ""),
    queryFn: () => endpoints.listInvitations(orgId!),
    enabled: !!orgId && enabled,
  });
}

/** Membership mutations invalidate members + invitations together — an
 * accepted or revoked invite changes both lists. */
function useMembershipInvalidation(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: entitlementKeys.snapshot(orgId ?? "") }),
      queryClient.invalidateQueries({ queryKey: orgKeys.members(orgId ?? "") }),
      queryClient.invalidateQueries({ queryKey: orgKeys.invitations(orgId ?? "") }),
    ]);
}

export function useInviteMember(orgId: string | undefined) {
  const invalidate = useMembershipInvalidation(orgId);
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: Role }) =>
      endpoints.inviteMember(orgId!, email, role),
    onSuccess: invalidate,
  });
}

export function useChangeMemberRole(orgId: string | undefined) {
  const invalidate = useMembershipInvalidation(orgId);
  return useMutation({
    mutationFn: ({ membershipId, role }: { membershipId: string; role: Role }) =>
      endpoints.changeMemberRole(orgId!, membershipId, role),
    onSuccess: invalidate,
  });
}

export function useRemoveMember(orgId: string | undefined) {
  const invalidate = useMembershipInvalidation(orgId);
  return useMutation({
    mutationFn: (membershipId: string) => endpoints.removeMember(orgId!, membershipId),
    onSuccess: invalidate,
  });
}

export function useRevokeInvitation(orgId: string | undefined) {
  const invalidate = useMembershipInvalidation(orgId);
  return useMutation({
    mutationFn: (invitationId: string) => endpoints.revokeInvitation(orgId!, invitationId),
    onSuccess: invalidate,
  });
}
