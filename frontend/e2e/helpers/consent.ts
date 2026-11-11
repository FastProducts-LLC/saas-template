import type { BrowserContext } from "@playwright/test";

import { CONSENT_VERSION } from "../../src/features/consent/model/store";
import { TOUR_KEYS } from "../../src/shared/lib/tours";

// Pre-seed the cookie-consent decision so the banner never overlays test
// clicks. Only cookie-consent.spec.ts starts without this.
export async function seedConsent(context: BrowserContext, analytics = false) {
  const record = JSON.stringify({
    version: CONSENT_VERSION,
    decidedAt: new Date().toISOString(),
    categories: { analytics },
  });
  await context.addInitScript((value: string) => {
    window.localStorage.setItem("cookieConsent", value);
  }, record);
}

// Mark all onboarding tours as seen — the dashboard tour's full-screen
// overlay (z-100) otherwise intercepts clicks for fresh users.
export async function seedToursSeen(context: BrowserContext) {
  await context.addInitScript((keys: string[]) => {
    for (const key of keys) window.localStorage.setItem(key, "true");
  }, Object.values(TOUR_KEYS));
}

// Standard pre-seed for tests that aren't about the banner or the tour.
export async function seedUiState(context: BrowserContext) {
  await seedConsent(context);
  await seedToursSeen(context);
}
