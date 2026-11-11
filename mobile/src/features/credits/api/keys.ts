export const creditKeys = {
  actions: ["credits", "actions"] as const,
  wallet: (orgId: string) => ["orgs", orgId, "credits", "wallet"] as const,
  history: (orgId: string) => ["orgs", orgId, "credits", "history"] as const,
};
