import { afterEach, describe, expect, it } from "vitest";

import { CONSENT_VERSION, consentAllows, getStoredConsent, storeConsent } from "./store";

afterEach(() => localStorage.clear());

describe("consent store", () => {
  it("returns null when nothing is stored", () => {
    expect(getStoredConsent()).toBeNull();
    expect(consentAllows("analytics")).toBe(false);
  });

  it("round-trips a decision", () => {
    storeConsent({ analytics: true });
    const record = getStoredConsent();
    expect(record?.version).toBe(CONSENT_VERSION);
    expect(record?.categories.analytics).toBe(true);
    expect(consentAllows("analytics")).toBe(true);
  });

  it("treats a rejection as a decision, not absence", () => {
    storeConsent({ analytics: false });
    expect(getStoredConsent()).not.toBeNull();
    expect(consentAllows("analytics")).toBe(false);
  });

  it("discards records from an older banner version (re-prompt)", () => {
    localStorage.setItem(
      "cookieConsent",
      JSON.stringify({
        version: "2000-01-01",
        decidedAt: new Date().toISOString(),
        categories: { analytics: true },
      }),
    );
    expect(getStoredConsent()).toBeNull();
    expect(consentAllows("analytics")).toBe(false);
  });

  it("survives corrupt storage", () => {
    localStorage.setItem("cookieConsent", "{not json");
    expect(getStoredConsent()).toBeNull();
  });
});
