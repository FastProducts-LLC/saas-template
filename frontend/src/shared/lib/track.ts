// Dual-sink product analytics facade — the ONLY analytics module call sites
// import. Event names come from ./events (generated from shared/events.toml).
//
// track(event, params) fans out to:
//   1. GA4            — only after the visitor granted analytics consent in
//                       the cookie banner AND a Measurement ID was built in.
//   2. first-party    — POST /api/events → the activity_events table. Only
//                       for a signed-in user; NOT gated on the cookie banner
//                       (nothing is stored on or read from the device — it is
//                       a server-side usage record under the user's session).
// Both sinks stop for a user who turned off "product analytics" in Profile
// (users.analytics_opt_out). That opt-out and cookie consent are independent:
// consent governs the GA tag for every visitor; opt-out silences analytics
// for one account. See docs/analytics.md.
//
// Rules for call sites
//   - Fire ONCE, at the success point (mutation onSuccess), never on click.
//   - Params are identifiers, enums, and numbers only. Never content, email,
//     tokens, or free text.
//   - Server-truth events (purchases, generation_completed, …) are written by
//     the backend. `track` only accepts client events, by type.
//
// Everything here is fire-and-forget: analytics must never throw into, slow
// down, or toast over the app.

import { getAccessToken } from "../api";
import * as ga from "./analytics";
import { GA_EVENT_ALIASES, type ClientEvent } from "./events";
import { getAnalyticsOptOutCache, setAnalyticsOptOutCache } from "./storage";

export type EventParams = Record<string, string | number | boolean | null | undefined>;

const INGEST_URL = "/api/events";

let currentUserId: string | null = null;
let optedOut = getAnalyticsOptOutCache();
let suspended = false;

// Opt-out must already hold on page load, before /auth/me resolves and
// before the consent hook (re)loads the tag for a consented visitor.
if (optedOut) ga.setGaDisabled(true);

function sendFirstParty(event: ClientEvent, properties?: EventParams): void {
  // Deliberately raw fetch, not api(): no retries, no Idempotency-Key, no
  // 401-refresh, and above all no global error toast for a dropped event.
  const token = getAccessToken();
  if (!currentUserId || !token) return;
  try {
    void fetch(INGEST_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ event, properties }),
      keepalive: true, // survives the Stripe redirect / page unload
    }).catch(() => {});
  } catch {
    // never throw into app code
  }
}

/** The one capture entry point. Fans out to every enabled sink. */
export function track(event: ClientEvent, params?: EventParams): void {
  if (optedOut || suspended) return;
  ga.gaTrack(GA_EVENT_ALIASES[event] ?? event, params);
  sendFirstParty(event, params);
}

/** Bind analytics to the signed-in user: call on login, on session restore,
 *  and whenever the user object is re-fetched (it carries the opt-out).
 *  Arms the first-party sink; GA gets a hashed id once/if consent loads it. */
export function identifyUser(user: { id: string; analytics_opt_out: boolean }): void {
  currentUserId = user.id;
  optedOut = user.analytics_opt_out;
  setAnalyticsOptOutCache(optedOut);
  ga.setGaDisabled(optedOut);
  if (optedOut) ga.clearAnalyticsUserId();
  else void ga.setAnalyticsUserId(user.id);
}

/** Call on successful logout. The opt-out cache is intentionally kept: on a
 *  shared browser, the person who objected stays un-tracked until someone
 *  else signs in (whose own setting then applies). */
export function resetAnalytics(): void {
  currentUserId = null;
  ga.clearAnalyticsUserId();
}

/** Pause every sink while a platform admin impersonates a user — the admin's
 *  clicks must not be recorded as the customer's activity (the impersonation
 *  token would attribute them to the customer server-side). */
export function setAnalyticsSuspended(value: boolean): void {
  suspended = value;
}

export function isAnalyticsOptedOut(): boolean {
  return optedOut;
}

// The GA-only surface, re-exported so nothing outside this file imports
// ./analytics: consent lifecycle (features/consent), bootstrap (main.tsx),
// and SPA page views (App.tsx). Page views are GA-only by design — the
// first-party table holds feature and business events, not traffic.
export {
  analyticsConfigured,
  denyAnalyticsConsent,
  grantAnalyticsConsent,
  initConsentMode,
  loadAnalytics,
  trackPageView,
} from "./analytics";
