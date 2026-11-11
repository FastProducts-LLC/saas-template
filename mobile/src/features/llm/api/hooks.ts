import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { creditKeys } from "../../credits";
import { LLM_TERMINAL_STATUSES, type LlmProvider } from "../model/types";
import * as endpoints from "./endpoints";
import { llmKeys } from "./keys";

const POLL_MS = 3000;

export function useLlmCalls(orgId: string | undefined) {
  return useQuery({
    queryKey: llmKeys.list(orgId ?? ""),
    queryFn: () => endpoints.listCalls(orgId!),
    enabled: !!orgId,
    refetchInterval: (query) => {
      const calls = query.state.data;
      return calls?.some((c) => !LLM_TERMINAL_STATUSES.has(c.status)) ? POLL_MS : false;
    },
  });
}

export function useLlmCall(orgId: string | undefined, callId: string | undefined) {
  return useQuery({
    queryKey: llmKeys.detail(orgId ?? "", callId ?? ""),
    queryFn: () => endpoints.getCall(orgId!, callId!),
    enabled: !!orgId && !!callId,
    refetchInterval: (query) => {
      const call = query.state.data;
      return call && !LLM_TERMINAL_STATUSES.has(call.status) ? POLL_MS : false;
    },
  });
}

export function useComplete(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, prompt }: { provider: LlmProvider; prompt: string }) =>
      endpoints.complete(orgId!, provider, prompt),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: llmKeys.list(orgId ?? "") }),
        queryClient.invalidateQueries({ queryKey: creditKeys.wallet(orgId ?? "") }),
      ]);
    },
  });
}
