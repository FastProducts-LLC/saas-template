export const adminEntitlementKeys = {
  org: (orgId: string) => ["admin", "entitlements", orgId] as const,
  revenue: ["admin", "revenue"] as const,
};
