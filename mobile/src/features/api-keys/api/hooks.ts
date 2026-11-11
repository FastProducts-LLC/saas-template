import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { entitlementKeys } from "../../entitlements";
import type { ApiKeyCreated } from "../model/types";
import * as endpoints from "./endpoints";
import { apiKeyKeys } from "./keys";

export function useApiKeys(orgId: string | undefined) {
  return useQuery({
    queryKey: apiKeyKeys.list(orgId ?? ""),
    queryFn: () => endpoints.listApiKeys(orgId!),
    enabled: !!orgId,
  });
}

export function useCreateApiKey(orgId: string | undefined, onCreated: (key: ApiKeyCreated) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => endpoints.createApiKey(orgId!, name),
    onSuccess: async (created) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: apiKeyKeys.list(orgId ?? "") }),
        queryClient.invalidateQueries({ queryKey: entitlementKeys.snapshot(orgId ?? "") }),
      ]);
      onCreated(created);
    },
  });
}

export function useDeleteApiKey(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => endpoints.deleteApiKey(orgId!, keyId),
    onSuccess: () => Promise.all([
      queryClient.invalidateQueries({ queryKey: apiKeyKeys.list(orgId ?? "") }),
      queryClient.invalidateQueries({ queryKey: entitlementKeys.snapshot(orgId ?? "") }),
    ]),
  });
}
