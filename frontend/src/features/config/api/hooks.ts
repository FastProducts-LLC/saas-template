import { useQuery } from "@tanstack/react-query";

import * as endpoints from "./endpoints";
import { configKeys } from "./keys";
import type { FeatureKey } from "../model/types";

export function useConfig() {
  return useQuery({
    queryKey: configKeys.all,
    queryFn: endpoints.getConfig,
    // Flags change rarely; the admin toggle invalidates this key explicitly.
    staleTime: 5 * 60_000,
  });
}

/** undefined while the config is loading, then the flag's effective value. */
export function useFeature(key: FeatureKey): boolean | undefined {
  const { data } = useConfig();
  return data ? Boolean(data.features[key]) : undefined;
}
