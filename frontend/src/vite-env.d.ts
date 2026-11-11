/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Sentry DSN for browser error tracking. Unset (the default) disables
   *  Sentry entirely — see src/shared/lib/sentry.ts. Baked in at build time
   *  (Vite inlines import.meta.env.*), so production sets it as a Docker
   *  build arg, not a runtime env var. */
  readonly VITE_SENTRY_DSN?: string;
  /** GA4 Measurement ID (G-XXXXXXXXXX). Unset (the default) disables
   *  analytics entirely — no gtag script, no consent banner. Baked in at
   *  build time as a Docker build arg — see src/shared/lib/analytics.ts. */
  readonly VITE_GA_MEASUREMENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
