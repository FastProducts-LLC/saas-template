/** Client-side consent record — the single source of truth for what the
 *  visitor allowed. For signed-in users the choice is additionally appended
 *  to the backend audit trail (api/hooks.ts); for anonymous visitors this
 *  localStorage record is the whole record.
 */

import type { ConsentCategories, StoredConsent } from "./types";

/** Bump when banner copy / category meanings change — everyone re-decides. */
export const CONSENT_VERSION = "2026-11-09";

const KEY = "cookieConsent";
const OPEN_EVENT = "app:open-cookie-settings";

export function getStoredConsent(): StoredConsent | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredConsent>;
    if (parsed.version !== CONSENT_VERSION || !parsed.decidedAt) return null;
    return {
      version: parsed.version,
      decidedAt: parsed.decidedAt,
      categories: { analytics: !!parsed.categories?.analytics },
    };
  } catch {
    return null;
  }
}

export function storeConsent(categories: ConsentCategories): StoredConsent {
  const record: StoredConsent = {
    version: CONSENT_VERSION,
    decidedAt: new Date().toISOString(),
    categories,
  };
  try {
    localStorage.setItem(KEY, JSON.stringify(record));
  } catch {
    // Storage unavailable (private mode) — the in-memory choice still applies
    // for this session; the banner will re-ask next visit.
  }
  return record;
}

/** Gate for non-essential loaders: any third-party analytics SDK must check
 *  this before loading. Undecided = false. (The first-party activity_events
 *  sink is deliberately NOT gated on this — it stores nothing on the device
 *  and has its own per-account opt-out; see shared/lib/track.ts.) */
export function consentAllows(category: keyof ConsentCategories): boolean {
  return getStoredConsent()?.categories[category] ?? false;
}

/** Re-opens the preferences dialog from anywhere (e.g. the footer link). */
export function openCookieSettings(): void {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

export function onOpenCookieSettings(handler: () => void): () => void {
  window.addEventListener(OPEN_EVENT, handler);
  return () => window.removeEventListener(OPEN_EVENT, handler);
}
