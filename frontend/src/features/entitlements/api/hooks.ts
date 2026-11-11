import { useQuery } from "@tanstack/react-query";
import { useOrg } from "../../organizations";
import { getEntitlements } from "./endpoints";
import { entitlementKeys } from "./keys";
import type { EntitlementKey } from "../model/types";
export function useEntitlements(orgId: string) {
  return useQuery({
    queryKey: entitlementKeys.org(orgId),
    queryFn: () => getEntitlements(orgId),
    enabled: !!orgId,
  });
}
export function useEntitlement(key: EntitlementKey) {
  const { currentOrg } = useOrg();
  const query = useEntitlements(currentOrg?.id ?? "");
  return { ...query, data: query.data?.entitlements.find((item) => item.key === key) };
}
