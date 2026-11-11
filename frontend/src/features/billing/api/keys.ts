// Query-key factory — the single source of truth for billing cache identity.

export const billingKeys = {
  plans: ["billing", "plans"] as const,
  plan: (orgId: string) => ["orgs", orgId, "billing-plan"] as const,
  account: (orgId: string) => ["orgs", orgId, "billing-account"] as const,
  invoices: (orgId: string) => ["orgs", orgId, "invoices"] as const,
};
