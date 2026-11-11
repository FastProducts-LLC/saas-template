export const billingKeys = {
  plan: (orgId: string) => ["orgs", orgId, "billing", "plan"] as const,
  packs: ["billing", "packs"] as const,
  account: (orgId: string) => ["orgs", orgId, "billing", "account"] as const,
  invoices: (orgId: string) => ["orgs", orgId, "billing", "invoices"] as const,
};
