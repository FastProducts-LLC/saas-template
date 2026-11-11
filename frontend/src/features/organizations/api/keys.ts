// Query-key factory — the single source of truth for org cache identity.

export const orgKeys = {
  all: ["orgs"] as const,
  members: (orgId: string) => ["orgs", orgId, "members"] as const,
  invitations: (orgId: string) => ["orgs", orgId, "invitations"] as const,
};
