// Typed localStorage access — the only place storage keys are spelled out.

const CURRENT_ORG_KEY = "currentOrgId";

export const getStoredOrgId = (): string | null => localStorage.getItem(CURRENT_ORG_KEY);

export const setStoredOrgId = (orgId: string) => localStorage.setItem(CURRENT_ORG_KEY, orgId);

export const clearStoredOrgId = () => localStorage.removeItem(CURRENT_ORG_KEY);

// Cache of the signed-in user's server-side analytics opt-out (users.
// analytics_opt_out is the source of truth). Cached so the GA kill switch is
// already on at page load, before /auth/me resolves. Guarded: storage can be
// unavailable (private mode), and analytics must never throw into the app.
const ANALYTICS_OPT_OUT_KEY = "analyticsOptOut";

export function getAnalyticsOptOutCache(): boolean {
  try {
    return localStorage.getItem(ANALYTICS_OPT_OUT_KEY) === "1";
  } catch {
    return false;
  }
}

export function setAnalyticsOptOutCache(optOut: boolean): void {
  try {
    if (optOut) localStorage.setItem(ANALYTICS_OPT_OUT_KEY, "1");
    else localStorage.removeItem(ANALYTICS_OPT_OUT_KEY);
  } catch {
    // in-memory state in track.ts still applies for this page load
  }
}
