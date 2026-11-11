export const apiKeyKeys = {
  list: (orgId: string) => ["orgs", orgId, "api-keys"] as const,
};
