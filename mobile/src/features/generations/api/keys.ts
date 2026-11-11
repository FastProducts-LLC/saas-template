export const generationKeys = {
  list: (orgId: string) => ["orgs", orgId, "generations"] as const,
  detail: (orgId: string, generationId: string) =>
    ["orgs", orgId, "generations", generationId] as const,
  file: (orgId: string, generationId: string) =>
    ["orgs", orgId, "generations", generationId, "file"] as const,
};
