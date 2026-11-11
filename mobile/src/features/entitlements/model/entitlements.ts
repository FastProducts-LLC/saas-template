import type { Entitlement } from "./types";

export function isIncluded(entitlement: Entitlement): boolean {
  return entitlement.limit === null || entitlement.limit > 0;
}

export function isAtLimit(entitlement: Entitlement): boolean {
  return entitlement.limit !== null && entitlement.used >= entitlement.limit;
}

export function remaining(entitlement: Entitlement): number | null {
  return entitlement.limit === null ? null : Math.max(0, entitlement.limit - entitlement.used);
}

export function formatLimit(limit: number | null): string {
  return limit === null ? "Unlimited" : limit.toLocaleString("en-US");
}

export const PLAN_LIMIT_MESSAGE = "The plan limit has been reached. Plans are managed in the web app.";
