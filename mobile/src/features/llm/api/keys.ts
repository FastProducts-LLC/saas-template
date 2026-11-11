export const llmKeys = {
  list: (orgId: string) => ["orgs", orgId, "llm", "calls"] as const,
  detail: (orgId: string, callId: string) => ["orgs", orgId, "llm", "calls", callId] as const,
};
