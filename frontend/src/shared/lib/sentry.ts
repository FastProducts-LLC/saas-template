/** Browser error tracking — mirrors the backend's Sentry setup
 *  (app/core/observability.py): a no-op unless a DSN is configured.
 *
 *  The DSN is inlined at build time (`VITE_SENTRY_DSN` build arg in CI);
 *  a DSN is client-visible by design, so it lives in a GitHub Actions
 *  variable rather than a secret. The CSP in caddy.d/myapp.caddy allows
 *  *.sentry.io — keep that in sync if the ingest host ever changes.
 *
 *  Never send full consumer-record / privacy-request payloads — beforeSend
 *  redacts request bodies and sensitive keys.
 */

import * as Sentry from "@sentry/react";

const SENSITIVE_KEY =
  /email|phone|password|token|secret|authorization|cookie|consumer_key|request_payload|addresses|emails|phones|device_ids|date_of_birth/i;

// Sentry's documented deny-list for reproducing the v10 `sendDefaultPii: false`
// header/query scrubbing (client IP and forwarding metadata).
const PII_HEADER_PATTERNS = ["forwarded", "-ip", "remote-", "via", "-user"];

function scrubValue(value: unknown, key?: string): unknown {
  if (key && SENSITIVE_KEY.test(key)) return "[redacted]";
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    if ("consumer_key" in obj && ("emails" in obj || "phones" in obj || "addresses" in obj)) {
      return { _redacted: "consumer_record" };
    }
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj)) out[k] = scrubValue(v, k);
    return out;
  }
  if (Array.isArray(value)) {
    return value.slice(0, 20).map((v) => scrubValue(v));
  }
  if (typeof value === "string" && value.length > 2000) {
    return `${value.slice(0, 2000)}…[truncated]`;
  }
  return value;
}

export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1, // parity with SENTRY_TRACES_SAMPLE_RATE default
    // Parity with the backend: no PII by default. Sentry v11 replaced
    // `sendDefaultPii` with `dataCollection`, and its defaults are permissive
    // (user info, cookies, request/response bodies) — so every category is
    // pinned off here rather than left unset.
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: {
        request: { deny: PII_HEADER_PATTERNS },
        response: { deny: PII_HEADER_PATTERNS },
      },
      httpBodies: [],
      urlQueryParams: { deny: PII_HEADER_PATTERNS },
      genAI: { inputs: false, outputs: false },
      databaseQueryData: false,
      queues: false,
      graphQL: { document: false, variables: false },
    },
    beforeSend(event) {
      if (event.request) {
        if (event.request.data) event.request.data = "[redacted]";
        if (event.request.cookies) event.request.cookies = {};
      }
      if (event.extra) event.extra = scrubValue(event.extra) as Record<string, unknown>;
      if (event.contexts) {
        event.contexts = scrubValue(event.contexts) as typeof event.contexts;
      }
      return event;
    },
  });
}
