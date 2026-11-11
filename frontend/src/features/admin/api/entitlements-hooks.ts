import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { entitlementKeys, type EntitlementKey } from "../../entitlements";
import type { OverridePayload } from "../model/entitlements";
import * as endpoints from "./entitlements-endpoints";
import { adminEntitlementKeys } from "./entitlements-keys";
export const useAdminRevenue = () =>
  useQuery({ queryKey: adminEntitlementKeys.revenue, queryFn: endpoints.getRevenue });
export const useAdminEntitlements = (orgId: string) =>
  useQuery({
    queryKey: adminEntitlementKeys.org(orgId),
    queryFn: () => endpoints.getOrgEntitlements(orgId),
    enabled: !!orgId,
  });
export function useOverrideMutations(orgId: string) {
  const client = useQueryClient();
  const onSuccess = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: adminEntitlementKeys.org(orgId) }),
      client.invalidateQueries({ queryKey: entitlementKeys.org(orgId) }),
    ]);
  const save = useMutation({
    mutationFn: ({ key, payload }: { key: EntitlementKey; payload: OverridePayload }) =>
      endpoints.setOverride(orgId, key, payload),
    onSuccess,
  });
  const remove = useMutation({
    mutationFn: (key: EntitlementKey) => endpoints.removeOverride(orgId, key),
    onSuccess,
  });
  return { save, remove };
}
