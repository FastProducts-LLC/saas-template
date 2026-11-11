import { api } from "../../../shared/api";

import type { ConsentCategories } from "../model/types";

export interface ServerConsent {
  analytics: boolean;
  policy_version: string;
  recorded_at: string;
}

/** Latest audit-trail entry for the signed-in user, or null if undecided. */
export function fetchServerConsent(): Promise<ServerConsent | null> {
  return api<ServerConsent | null>("/consent");
}

export function recordServerConsent(
  categories: ConsentCategories,
  policyVersion: string,
): Promise<ServerConsent> {
  return api<ServerConsent>("/consent", {
    method: "POST",
    body: JSON.stringify({ analytics: categories.analytics, policy_version: policyVersion }),
  });
}
