export const entitlementKeys = {
  all: ["entitlements"] as const,
  org: (orgId: string) => ["entitlements", orgId] as const,
};
