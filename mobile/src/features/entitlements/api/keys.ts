export const entitlementKeys = {
  snapshot: (orgId: string) => ["orgs", orgId, "entitlements"] as const,
};
