import { useQuery } from "@tanstack/react-query";
import { getEntitlements } from "./endpoints";
import { entitlementKeys } from "./keys";

export function useEntitlements(orgId: string | undefined) {
  return useQuery({
    queryKey: entitlementKeys.snapshot(orgId ?? ""),
    queryFn: () => getEntitlements(orgId!),
    enabled: !!orgId,
  });
}
