import { afterEach, describe, expect, it, vi } from "vitest";

// analytics.ts keeps module-level state (script-loaded flag, last tracked
// path), so every test re-imports it through a fresh registry.
async function freshAnalytics() {
  vi.resetModules();
  return await import("./analytics");
}

afterEach(() => {
  vi.unstubAllEnvs();
  document.querySelectorAll('script[src*="googletagmanager"]').forEach((s) => s.remove());
  // Reset the shared dataLayer so consent/event entries don't leak across tests.
  window.dataLayer = [];
});

function dataLayerEvents(name: string) {
  return (window.dataLayer ?? [])
    .filter((entry) => Array.isArray(entry) && entry[0] === "event" && entry[1] === name)
    .map((e) => (e as unknown[])[2]);
}

function dataLayerEntries(command: string) {
  return (window.dataLayer ?? []).filter(
    (entry) => Array.isArray(entry) && entry[0] === command,
  ) as unknown[][];
}

describe("loadAnalytics", () => {
  it("is inert without a Measurement ID", async () => {
    const analytics = await freshAnalytics();
    analytics.loadAnalytics();
    expect(document.querySelector('script[src*="googletagmanager"]')).toBeNull();
  });

  it("injects gtag exactly once when configured", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const analytics = await freshAnalytics();
    analytics.loadAnalytics();
    analytics.loadAnalytics();
    expect(document.querySelectorAll('script[src*="googletagmanager"]')).toHaveLength(1);
  });

  it("enables debug_mode in dev builds", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    vi.stubEnv("DEV", true);
    const analytics = await freshAnalytics();
    analytics.loadAnalytics();
    const configs = dataLayerEntries("config");
    const lastConfig = configs[configs.length - 1];
    expect((lastConfig[2] as Record<string, unknown>).debug_mode).toBe(true);
  });
});

describe("sanitizePath", () => {
  it("masks id-like path segments and keeps everything else", async () => {
    const analytics = await freshAnalytics();
    expect(analytics.sanitizePath("/items/8f14e45f-ceea-4670-9f4a-6b3c1e6f2a01")).toBe(
      "/items/:id",
    );
    expect(analytics.sanitizePath("/invoices/4821")).toBe("/invoices/:id");
    expect(analytics.sanitizePath("/items/rec_5551234567")).toBe("/items/:id");
    expect(analytics.sanitizePath("/t/a1b2c3d4e5f6a7b8c9")).toBe("/t/:id");
    // Word slugs with digits stay readable — they are routes, not subjects.
    expect(analytics.sanitizePath("/top-10-templates")).toBe("/top-10-templates");
    expect(analytics.sanitizePath("/2fa-setup")).toBe("/2fa-setup");
    expect(analytics.sanitizePath("/items/at-address")).toBe("/items/at-address");
    expect(analytics.sanitizePath("/items")).toBe("/items");
    expect(analytics.sanitizePath("/pricing")).toBe("/pricing");
  });

  it("page_view events carry the sanitized path and no query string", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const analytics = await freshAnalytics();
    analytics.loadAnalytics();
    analytics.trackPageView("/items/rec_55512345");
    const pageViews = dataLayerEvents("page_view");
    const last = pageViews[pageViews.length - 1] as {
      page_path: string;
      page_location: string;
    };
    expect(last.page_path).toBe("/items/:id");
    expect(last.page_location).not.toContain("rec_55512345");
    expect(last.page_location).not.toContain("?");
  });
});

describe("Consent Mode v2", () => {
  it("initConsentMode sets default denied state", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.initConsentMode();
    const consents = dataLayerEntries("consent");
    expect(consents.length).toBeGreaterThanOrEqual(1);
    const defaults = consents.find((c) => c[1] === "default");
    expect(defaults).toBeTruthy();
    expect((defaults![2] as Record<string, string>).analytics_storage).toBe("denied");
  });

  it("initConsentMode is idempotent", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.initConsentMode();
    a.initConsentMode();
    const consents = dataLayerEntries("consent").filter((c) => c[1] === "default");
    expect(consents).toHaveLength(1);
  });

  it("grantAnalyticsConsent updates to granted", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.initConsentMode();
    a.grantAnalyticsConsent();
    const updates = dataLayerEntries("consent").filter((c) => c[1] === "update");
    expect(updates).toHaveLength(1);
    expect((updates[0][2] as Record<string, string>).analytics_storage).toBe("granted");
  });

  it("denyAnalyticsConsent updates to denied", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.initConsentMode();
    a.grantAnalyticsConsent();
    a.denyAnalyticsConsent();
    const updates = dataLayerEntries("consent").filter((c) => c[1] === "update");
    expect(updates).toHaveLength(2);
    expect((updates[1][2] as Record<string, string>).analytics_storage).toBe("denied");
  });

  it("is inert without a Measurement ID", async () => {
    const before = window.dataLayer?.length ?? 0;
    const a = await freshAnalytics();
    a.initConsentMode();
    a.grantAnalyticsConsent();
    a.denyAnalyticsConsent();
    expect(window.dataLayer?.length ?? 0).toBe(before);
  });
});

describe("user identity", () => {
  it("setAnalyticsUserId hashes the id", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.loadAnalytics();
    await a.setAnalyticsUserId("test-user-uuid");
    const sets = dataLayerEntries("set");
    const userIdSet = sets.find(
      (s) => typeof s[1] === "object" && s[1] !== null && "user_id" in (s[1] as object),
    );
    expect(userIdSet).toBeTruthy();
    const uid = (userIdSet![1] as Record<string, string>).user_id;
    expect(uid).not.toBe("test-user-uuid");
    expect(uid).toMatch(/^[a-f0-9]{64}$/);
  });

  it("clearAnalyticsUserId sets user_id to null", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.loadAnalytics();
    a.clearAnalyticsUserId();
    const sets = dataLayerEntries("set");
    const cleared = sets.find(
      (s) =>
        typeof s[1] === "object" &&
        s[1] !== null &&
        "user_id" in (s[1] as object) &&
        (s[1] as Record<string, unknown>).user_id === null,
    );
    expect(cleared).toBeTruthy();
  });
});

describe("user properties", () => {
  it("setUserProperties pushes to dataLayer", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.loadAnalytics();
    a.setUserProperties({ account_type: "paid", org_role: "admin" });
    const sets = dataLayerEntries("set");
    const propSet = sets.find((s) => s[1] === "user_properties");
    expect(propSet).toBeTruthy();
    expect(propSet![2]).toEqual({ account_type: "paid", org_role: "admin" });
  });

  it("is a no-op when analytics is not loaded", async () => {
    const before = window.dataLayer?.length ?? 0;
    const a = await freshAnalytics();
    a.setUserProperties({ account_type: "free" });
    expect(window.dataLayer?.length ?? 0).toBe(before);
  });
});

describe("gaTrack", () => {
  it("pushes the event and params once the tag is loaded", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.loadAnalytics();
    a.gaTrack("invite_sent", { role: "admin" });
    expect(dataLayerEvents("invite_sent")).toEqual([{ role: "admin" }]);
  });

  it("is a no-op before consent loaded the tag", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.gaTrack("org_created");
    expect(dataLayerEvents("org_created")).toHaveLength(0);
  });

  it("is a no-op without a Measurement ID", async () => {
    const before = window.dataLayer?.length ?? 0;
    const a = await freshAnalytics();
    a.loadAnalytics();
    a.gaTrack("org_created");
    expect(window.dataLayer?.length ?? 0).toBe(before);
  });
});

describe("per-user kill switch", () => {
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>)["ga-disable-G-TEST123"];
  });

  it("setGaDisabled sets GA's ga-disable flag and silences gaTrack", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.loadAnalytics();
    a.setGaDisabled(true);
    expect((window as unknown as Record<string, unknown>)["ga-disable-G-TEST123"]).toBe(true);
    a.gaTrack("org_created");
    expect(dataLayerEvents("org_created")).toHaveLength(0);

    a.setGaDisabled(false);
    expect((window as unknown as Record<string, unknown>)["ga-disable-G-TEST123"]).toBe(false);
    a.gaTrack("org_created");
    expect(dataLayerEvents("org_created")).toHaveLength(1);
  });

  it("while disabled, consent does not fetch gtag.js; opting back in loads it", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.setGaDisabled(true); // opted-out account (from the cache, at page load)
    a.loadAnalytics(); // the visitor had accepted cookies earlier
    expect(document.querySelector('script[src*="googletagmanager"]')).toBeNull();
    expect(dataLayerEvents("page_view")).toHaveLength(0);

    a.setGaDisabled(false); // user opts back in
    expect(document.querySelectorAll('script[src*="googletagmanager"]')).toHaveLength(1);
    expect(dataLayerEvents("page_view")).toHaveLength(1);
  });

  it("releasing the switch does not load the tag when consent never asked for it", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.setGaDisabled(true);
    a.setGaDisabled(false);
    expect(document.querySelector('script[src*="googletagmanager"]')).toBeNull();
  });

  it("page views stop while disabled on an already-loaded tag", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    a.loadAnalytics();
    const before = dataLayerEvents("page_view").length;
    a.setGaDisabled(true);
    a.trackPageView("/billing");
    expect(dataLayerEvents("page_view")).toHaveLength(before);
  });

  it("does not touch window when GA is not configured", async () => {
    const a = await freshAnalytics();
    a.setGaDisabled(true);
    expect(Object.keys(window).filter((k) => k.startsWith("ga-disable-"))).toEqual([]);
  });
});

describe("identity requested before consent", () => {
  function userIdSets() {
    return dataLayerEntries("set")
      .map((s) => s[1])
      .filter(
        (v): v is { user_id: unknown } => typeof v === "object" && v !== null && "user_id" in v,
      )
      .map((v) => v.user_id);
  }

  it("is replayed when the tag loads later (login, then Accept)", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    await a.setAnalyticsUserId("user-1"); // logged in, banner not yet answered
    expect(userIdSets()).toEqual([]);
    a.loadAnalytics(); // visitor accepts
    await vi.waitFor(() => expect(userIdSets()).toHaveLength(1));
    expect(userIdSets()[0]).toMatch(/^[a-f0-9]{64}$/);
  });

  it("is not replayed after logout", async () => {
    vi.stubEnv("VITE_GA_MEASUREMENT_ID", "G-TEST123");
    const a = await freshAnalytics();
    await a.setAnalyticsUserId("user-1");
    a.clearAnalyticsUserId();
    a.loadAnalytics();
    await new Promise((r) => setTimeout(r, 20));
    expect(userIdSets().filter((v) => v !== null)).toEqual([]);
  });
});
