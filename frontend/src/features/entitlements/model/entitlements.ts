export const isIncluded = (limit: number | null) => limit === null || limit > 0;
export const remaining = (limit: number | null, used: number) =>
  limit === null ? null : Math.max(0, limit - used);
export const isAtLimit = (limit: number | null, used: number) => limit !== null && used >= limit;
export const formatLimit = (limit: number | null) => (limit === null ? "Unlimited" : String(limit));
