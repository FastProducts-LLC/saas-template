import { entitlementKeys } from "../../entitlements";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EVENTS } from "../../../shared/lib/events";
import { track } from "../../../shared/lib/track";
import * as endpoints from "./endpoints";
import { apiKeyKeys } from "./keys";
import type { ApiKeyCreatePayload } from "../model/types";

export function useApiKeys(orgId: string) {
  return useQuery({
    queryKey: apiKeyKeys.all(orgId),
    queryFn: () => endpoints.listApiKeys(orgId),
  });
}

export function useCreateApiKey(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ApiKeyCreatePayload) => endpoints.createApiKey(orgId, payload),
    onSuccess: () => {
      track(EVENTS.api_key_created);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: apiKeyKeys.all(orgId) }),
        queryClient.invalidateQueries({ queryKey: entitlementKeys.org(orgId) }),
      ]);
    },
  });
}

export function useRevokeApiKey(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => endpoints.revokeApiKey(orgId, keyId),
    onSuccess: () => {
      track(EVENTS.api_key_revoked);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: apiKeyKeys.all(orgId) }),
        queryClient.invalidateQueries({ queryKey: entitlementKeys.org(orgId) }),
      ]);
    },
  });
}
