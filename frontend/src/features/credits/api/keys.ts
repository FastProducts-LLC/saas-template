// Query-key factory — the single source of truth for credits cache identity.
// `all(orgId)` prefixes every credits key so one invalidate refreshes both
// the wallet and the history after a hold/capture/release.

export const creditsKeys = {
  actionCosts: ["credit-action-costs"] as const,
  packs: ["credit-packs"] as const,
  all: (orgId: string) => ["orgs", orgId, "credits"] as const,
  wallet: (orgId: string) => ["orgs", orgId, "credits", "wallet"] as const,
  history: (orgId: string, page: number) => ["orgs", orgId, "credits", "history", page] as const,
  usage: (orgId: string, period: string) => ["orgs", orgId, "credits", "usage", period] as const,
};
