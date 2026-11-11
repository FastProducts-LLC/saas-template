export const apiKeyKeys = {
  all: (orgId: string) => ["api-keys", orgId] as const,
};
