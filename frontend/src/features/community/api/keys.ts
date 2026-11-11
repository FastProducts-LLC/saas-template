// The single source of truth for community cache identity. `all` is the
// prefix key — one invalidation refreshes everything after webhook-driven
// membership changes land.
export const communityKeys = {
  all: ["community"] as const,
  me: ["community", "me"] as const,
  directory: (search: string, page: number) => ["community", "members", search, page] as const,
  member: (handle: string) => ["community", "member", handle] as const,
  plans: ["community", "plans"] as const,
  conversations: ["community", "conversations"] as const,
  messages: (conversationId: string) => ["community", "messages", conversationId] as const,
};
