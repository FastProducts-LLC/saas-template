import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CONSENT_VERSION } from "../model/types";
import * as endpoints from "./endpoints";

const consentKey = ["consent"] as const;

export function useConsent() {
  const query = useQuery({ queryKey: consentKey, queryFn: endpoints.getConsent });
  // A consent recorded under an older policy version counts as undecided.
  const current =
    query.data && query.data.policy_version === CONSENT_VERSION ? query.data : null;
  return { ...query, consent: current };
}

export function useRecordConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endpoints.recordConsent,
    onSuccess: (recorded) => queryClient.setQueryData(consentKey, recorded),
  });
}
