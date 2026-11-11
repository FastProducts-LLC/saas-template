// Keep in sync with frontend/src/features/consent/model/store.ts — the
// backend stores whatever version string the client sends, and the web app
// re-prompts when the stored version differs.
export const CONSENT_VERSION = "2026-07-09";

export interface Consent {
  analytics: boolean;
  policy_version: string;
  recorded_at: string;
}
