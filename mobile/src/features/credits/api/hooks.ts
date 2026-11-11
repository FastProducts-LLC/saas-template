import { useQuery } from "@tanstack/react-query";

import * as endpoints from "./endpoints";
import { creditKeys } from "./keys";

export function useActionCosts() {
  return useQuery({
    queryKey: creditKeys.actions,
    queryFn: endpoints.listActionCosts,
    staleTime: 60 * 60 * 1000, // costs change on deploys, not mid-session
  });
}

export function useWallet(orgId: string | undefined) {
  return useQuery({
    queryKey: creditKeys.wallet(orgId ?? ""),
    queryFn: () => endpoints.getWallet(orgId!),
    enabled: !!orgId,
  });
}

export function useCreditHistory(orgId: string | undefined, limit = 20) {
  return useQuery({
    queryKey: creditKeys.history(orgId ?? ""),
    queryFn: () => endpoints.getHistory(orgId!, limit),
    enabled: !!orgId,
  });
}
