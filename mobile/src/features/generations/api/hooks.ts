import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { creditKeys } from "../../credits";
import { TERMINAL_STATUSES, type Generation, type GenerationKind } from "../model/types";
import * as endpoints from "./endpoints";
import { generationKeys } from "./keys";

const POLL_MS = 4000;

/** Generation list; polls while any item is still in flight (202 → pending). */
export function useGenerations(orgId: string | undefined) {
  return useQuery({
    queryKey: generationKeys.list(orgId ?? ""),
    queryFn: () => endpoints.listGenerations(orgId!),
    enabled: !!orgId,
    refetchInterval: (query) => {
      const items = query.state.data;
      return items?.some((g) => !TERMINAL_STATUSES.has(g.status)) ? POLL_MS : false;
    },
  });
}

export function useGeneration(orgId: string | undefined, generationId: string | undefined) {
  return useQuery({
    queryKey: generationKeys.detail(orgId ?? "", generationId ?? ""),
    queryFn: () => endpoints.getGeneration(orgId!, generationId!),
    enabled: !!orgId && !!generationId,
    refetchInterval: (query) => {
      const g = query.state.data;
      return g && !TERMINAL_STATUSES.has(g.status) ? POLL_MS : false;
    },
  });
}

export function useGenerationFile(orgId: string | undefined, generation: Generation | undefined) {
  const ready =
    !!orgId && !!generation && generation.status === "succeeded" && generation.has_file;
  return useQuery({
    queryKey: generationKeys.file(orgId ?? "", generation?.id ?? ""),
    queryFn: () => endpoints.getGenerationFile(orgId!, generation!.id),
    enabled: ready,
    staleTime: Infinity, // result assets are immutable
  });
}

function useInvalidateGenerations(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: generationKeys.list(orgId ?? "") }),
      // Credits move on every reserve/capture/release.
      queryClient.invalidateQueries({ queryKey: creditKeys.wallet(orgId ?? "") }),
      queryClient.invalidateQueries({ queryKey: creditKeys.history(orgId ?? "") }),
    ]);
  };
}

export function useCreateGeneration(orgId: string | undefined) {
  const invalidate = useInvalidateGenerations(orgId);
  return useMutation({
    mutationFn: ({ kind, prompt }: { kind: GenerationKind; prompt: string }) =>
      endpoints.createGeneration(orgId!, kind, prompt),
    onSuccess: invalidate,
  });
}

export function useCancelGeneration(orgId: string | undefined) {
  const invalidate = useInvalidateGenerations(orgId);
  return useMutation({
    mutationFn: (generationId: string) => endpoints.cancelGeneration(orgId!, generationId),
    onSuccess: invalidate,
  });
}

export function useDeleteGeneration(orgId: string | undefined) {
  const invalidate = useInvalidateGenerations(orgId);
  return useMutation({
    mutationFn: (generationId: string) => endpoints.deleteGeneration(orgId!, generationId),
    onSuccess: invalidate,
  });
}
