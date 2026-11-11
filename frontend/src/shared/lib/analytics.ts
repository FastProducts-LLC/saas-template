// Google Analytics 4 (gtag.js) with Consent Mode v2 — the GA SINK only.
//
// Call sites never import this module: they import ./track, the dual-sink
// facade (GA + the first-party activity_events table). This file knows
// nothing about the first-party sink.
//
// The Measurement ID (G-XXXXXXXXXX) comes from a BUILD-TIME env var — Vite
// inlines import.meta.env.VITE_GA_MEASUREMENT_ID into the bundle (CI passes it
// as a Docker build arg). With no ID present the module is fully inert: no
// script, no banner, nothing sent — the safe default for dev builds.
//
// Consent Mode v2: on page load, initConsentMode() declares the default state
// (analytics_storage: denied). When the visitor grants analytics consent,
// grantAnalyticsConsent() flips it to "granted" and loadAnalytics() starts
// the full session. If consent is never given, GA4 still receives cookieless
// pings that fuel its behavioral modeling — no cookies are written.
//
// Privacy: user inputs can carry names/emails/phones in URL query strings.
// Query strings are therefore stripped from everything sent to GA, and
// id-carrying paths are normalized to their route pattern.

declare global {
  interface Window {
    dataLayer: unknown[];
  }
}

let consentModeInitialized = false;
let scriptLoaded = false;
let lastTrackedPath: string | null = null;
// Identity/properties requested before gtag loaded (login before the visitor
// accepted cookies). Replayed by loadAnalytics so accept-after-login still
// attributes the session.
let pendingUserId: string | null = null;
let disabled = false;
// Consent asked for the tag while the kill switch was on; honored if/when the
// switch is released (see setGaDisabled).
let loadDeferred = false;

type GtagFn = (...args: unknown[]) => void;
let gtagFn: GtagFn | null = null;

function measurementId(): string | undefined {
  return import.meta.env.VITE_GA_MEASUREMENT_ID;
}

/** True only when a Measurement ID was provided to this build. */
export function analyticsConfigured(): boolean {
  return Boolean(measurementId());
}

function isDebugBuild(): boolean {
  return !!import.meta.env.DEV;
}

function ensureGtag(): GtagFn {
  if (!gtagFn) {
    window.dataLayer = window.dataLayer || [];
    gtagFn = (...args: unknown[]) => {
      window.dataLayer.push(args);
    };
  }
  return gtagFn;
}

// --- Consent Mode v2 --------------------------------------------------------

/** Declare the default consent state before any Google tag loads. Call once on
 *  page load, regardless of whether the user has consented. This enables GA4's
 *  behavioral modeling for users who never consent. */
export function initConsentMode(): void {
  if (!analyticsConfigured() || consentModeInitialized) return;
  consentModeInitialized = true;
  const gtag = ensureGtag();
  gtag("consent", "default", {
    analytics_storage: "denied",
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    wait_for_update: 500,
  });
}

/** Update consent state to granted. Called by the consent hook after the
 *  visitor opts in. */
export function grantAnalyticsConsent(): void {
  if (!analyticsConfigured()) return;
  const gtag = ensureGtag();
  gtag("consent", "update", { analytics_storage: "granted" });
}

/** Revoke analytics consent (visitor changed their mind). */
export function denyAnalyticsConsent(): void {
  if (!analyticsConfigured()) return;
  const gtag = ensureGtag();
  gtag("consent", "update", { analytics_storage: "denied" });
}

// --- Path sanitization --------------------------------------------------------

// Query strings can contain user inputs (names, emails, phones) and tokens
// (reset-password, invitations); resource ids are per-subject. None of it may
// reach Google — send the route shape only: id-like path segments are masked
// to ":id". The heuristic covers UUIDs, pure-numeric ids, prefixed ids
// (inv_8f3a2), and long opaque tokens, while leaving word slugs alone
// (/top-10-templates). If your routes use another id shape, extend
// isIdSegment — and add a test in analytics.test.ts.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const NUMERIC_RE = /^\d+$/;
const PREFIXED_ID_RE = /^[A-Za-z]+_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+$/;
const OPAQUE_TOKEN_RE = /^(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{16,}$/;

function isIdSegment(segment: string): boolean {
  return (
    UUID_RE.test(segment) ||
    NUMERIC_RE.test(segment) ||
    PREFIXED_ID_RE.test(segment) ||
    OPAQUE_TOKEN_RE.test(segment)
  );
}

export function sanitizePath(pathname: string): string {
  return pathname
    .split("/")
    .map((segment) => (segment && isIdSegment(segment) ? ":id" : segment))
    .join("/");
}

// --- gtag bootstrap ----------------------------------------------------------

/** Inject gtag.js and start a session. Idempotent; no-op when GA isn't
 *  configured. Call only after consent. Config uses send_page_view:false so
 *  SPA navigation is the single source of page_views. */
export function loadAnalytics(): void {
  const id = measurementId();
  if (!id || scriptLoaded) return;
  if (disabled) {
    // An opted-out account: don't even fetch gtag.js (that request alone
    // tells Google about the visit). Load later if the user opts back in.
    loadDeferred = true;
    return;
  }
  loadDeferred = false;
  scriptLoaded = true;

  const gtag = ensureGtag();

  const s = document.createElement("script");
  s.async = true;
  // Host must stay allowed by the CSP in caddy.d/myapp.caddy (script-src).
  s.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  document.head.appendChild(s);

  gtag("js", new Date());
  gtag("config", id, {
    send_page_view: false,
    anonymize_ip: true,
    debug_mode: isDebugBuild(),
  });

  if (pendingUserId) void setAnalyticsUserId(pendingUserId);
  trackPageView(window.location.pathname);
}

// --- Per-user kill switch ----------------------------------------------------

/** GA's documented opt-out flag (window['ga-disable-<ID>']): while true,
 *  gtag.js sends nothing, even if it is already loaded. Driven by the
 *  signed-in user's analytics opt-out — independent of cookie consent, which
 *  decides whether the tag loads at all. */
export function setGaDisabled(value: boolean): void {
  disabled = value;
  const id = measurementId();
  if (!id) return;
  (window as unknown as Record<string, unknown>)[`ga-disable-${id}`] = value;
  if (!value && loadDeferred) loadAnalytics();
}

// --- User identity -----------------------------------------------------------

/** Set GA4 user_id for cross-device reporting. The raw UUID is hashed so the
 *  internal id never leaves the client in cleartext. */
export async function setAnalyticsUserId(userId: string): Promise<void> {
  if (!analyticsConfigured()) return;
  pendingUserId = userId;
  if (!scriptLoaded) return; // replayed by loadAnalytics after consent
  const hash = await sha256(userId);
  // The user may have logged out (or switched) while the hash was computing.
  if (pendingUserId !== userId) return;
  ensureGtag()("set", { user_id: hash });
}

export function clearAnalyticsUserId(): void {
  pendingUserId = null;
  if (!analyticsConfigured()) return;
  ensureGtag()("set", { user_id: null });
}

async function sha256(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// --- User properties ---------------------------------------------------------

export interface AnalyticsUserProperties {
  account_type?: "free" | "paid";
  org_role?: "owner" | "admin" | "member";
}

export function setUserProperties(props: AnalyticsUserProperties): void {
  if (!scriptLoaded || !analyticsConfigured()) return;
  ensureGtag()("set", "user_properties", props);
}

// --- Page views --------------------------------------------------------------

/** Fire a SPA page_view. No-op until gtag is loaded; de-dupes repeat paths. */
export function trackPageView(pathname: string): void {
  if (!scriptLoaded || disabled || !analyticsConfigured()) return;
  const path = sanitizePath(pathname);
  if (path === lastTrackedPath) return;
  lastTrackedPath = path;
  ensureGtag()("event", "page_view", {
    page_path: path,
    page_location: window.location.origin + path,
    page_title: document.title,
  });
}

// --- Custom events -----------------------------------------------------------

/** Send one event to GA. No-op until consent loaded the tag, and while the
 *  per-user kill switch is on. `name` is the GA-facing name (track.ts applies
 *  the registry's GA aliases). Params must never contain personal data. */
export function gaTrack(name: string, params?: Record<string, unknown>): void {
  if (!scriptLoaded || disabled || !analyticsConfigured()) return;
  ensureGtag()("event", name, params || {});
}
