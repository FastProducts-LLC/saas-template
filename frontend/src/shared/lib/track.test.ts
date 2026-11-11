import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// track.ts keeps module-level state (identity, opt-out, suspension) and reads
// the opt-out cache at import time, so every test imports a fresh copy.

const gaMock = {
  gaTrack: vi.fn(),
  setGaDisabled: vi.fn(),
  setAnalyticsUserId: vi.fn().mockResolvedValue(undefined),
  clearAnalyticsUserId: vi.fn(),
  analyticsConfigured: vi.fn(() => true),
  denyAnalyticsConsent: vi.fn(),
  grantAnalyticsConsent: vi.fn(),
  initConsentMode: vi.fn(),
  loadAnalytics: vi.fn(),
  trackPageView: vi.fn(),
};
let accessToken: string | null = "tok-1";

vi.mock("./analytics", () => gaMock);
vi.mock("../api", () => ({ getAccessToken: () => accessToken }));

const fetchMock = vi.fn();

async function freshTrack() {
  vi.resetModules();
  return await import("./track");
}

const USER = { id: "u1", analytics_opt_out: false };
const OPTED_OUT = { id: "u1", analytics_opt_out: true };

function sentBodies() {
  return fetchMock.mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  accessToken = "tok-1";
  fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("track() sink matrix", () => {
  it("anonymous visitor: GA only, nothing first-party", async () => {
    const t = await freshTrack();
    t.track("cta_clicked", { cta: "primary", location: "hero" });
    expect(gaMock.gaTrack).toHaveBeenCalledWith("cta_clicked", {
      cta: "primary",
      location: "hero",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("signed-in user: both sinks, authenticated as the session", async () => {
    const t = await freshTrack();
    t.identifyUser(USER);
    t.track("invite_sent", { role: "admin" });

    expect(gaMock.gaTrack).toHaveBeenCalledWith("invite_sent", { role: "admin" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/events");
    expect(init.method).toBe("POST");
    expect(init.keepalive).toBe(true);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok-1");
    // The user id is never in the payload — the server takes it from the session.
    expect(JSON.parse(init.body as string)).toEqual({
      event: "invite_sent",
      properties: { role: "admin" },
    });
  });

  it("identified but no access token yet: GA only (no doomed 401)", async () => {
    const t = await freshTrack();
    t.identifyUser(USER);
    accessToken = null;
    t.track("org_created");
    expect(gaMock.gaTrack).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("after logout: back to GA only", async () => {
    const t = await freshTrack();
    t.identifyUser(USER);
    t.resetAnalytics();
    t.track("cta_clicked");
    expect(gaMock.clearAnalyticsUserId).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(gaMock.gaTrack).toHaveBeenCalledTimes(1);
  });
});

describe("GA aliases", () => {
  it("sends GA its recommended name, the table the registry name", async () => {
    const t = await freshTrack();
    t.identifyUser(USER);
    t.track("user_signed_up", { method: "email", marketing_opt_in: false });
    t.track("user_logged_in", { method: "email" });
    t.track("checkout_started", { product: "credit_pack", plan: "growth" });

    expect(gaMock.gaTrack.mock.calls.map(([name]) => name)).toEqual([
      "sign_up",
      "login",
      "begin_checkout",
    ]);
    expect(sentBodies().map((b) => b.event)).toEqual([
      "user_signed_up",
      "user_logged_in",
      "checkout_started",
    ]);
  });
});

describe("opt-out", () => {
  it("an opted-out user sends nothing to either sink and GA is disabled", async () => {
    const t = await freshTrack();
    t.identifyUser(OPTED_OUT);
    t.track("org_created");

    expect(t.isAnalyticsOptedOut()).toBe(true);
    expect(gaMock.setGaDisabled).toHaveBeenLastCalledWith(true);
    expect(gaMock.setAnalyticsUserId).not.toHaveBeenCalled();
    expect(gaMock.clearAnalyticsUserId).toHaveBeenCalled();
    expect(gaMock.gaTrack).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("survives a reload: GA is disabled at import, before /auth/me resolves", async () => {
    (await freshTrack()).identifyUser(OPTED_OUT);
    vi.clearAllMocks();

    const reloaded = await freshTrack(); // new page load, nobody identified yet
    expect(gaMock.setGaDisabled).toHaveBeenCalledWith(true);
    reloaded.track("cta_clicked");
    expect(gaMock.gaTrack).not.toHaveBeenCalled();
  });

  it("opting back in re-enables both sinks", async () => {
    const t = await freshTrack();
    t.identifyUser(OPTED_OUT);
    t.identifyUser(USER);
    t.track("org_created");
    expect(gaMock.setGaDisabled).toHaveBeenLastCalledWith(false);
    expect(gaMock.gaTrack).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    vi.clearAllMocks();
    await freshTrack();
    expect(gaMock.setGaDisabled).not.toHaveBeenCalledWith(true);
  });

  it("the next user's own setting replaces a cached opt-out", async () => {
    const t = await freshTrack();
    t.identifyUser(OPTED_OUT);
    t.resetAnalytics();
    t.track("cta_clicked"); // logged out, cache still protects the objector
    expect(gaMock.gaTrack).not.toHaveBeenCalled();

    t.identifyUser({ id: "u2", analytics_opt_out: false });
    t.track("org_created");
    expect(gaMock.gaTrack).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("impersonation", () => {
  it("suspension silences both sinks and lifts cleanly", async () => {
    const t = await freshTrack();
    t.identifyUser(USER);
    t.setAnalyticsSuspended(true);
    t.track("api_key_created");
    expect(gaMock.gaTrack).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();

    t.setAnalyticsSuspended(false);
    t.track("api_key_created");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("failure isolation", () => {
  it("a rejected, throwing, or non-2xx ingest never reaches the caller", async () => {
    const t = await freshTrack();
    t.identifyUser(USER);

    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    expect(() => t.track("org_created")).not.toThrow();

    fetchMock.mockImplementationOnce(() => {
      throw new Error("fetch exploded synchronously");
    });
    expect(() => t.track("org_created")).not.toThrow();

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));
    expect(() => t.track("org_created")).not.toThrow();
    await new Promise((r) => setTimeout(r, 0)); // let rejections settle unhandled-free
  });

  it("works when localStorage is unavailable", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const t = await freshTrack();
    expect(() => t.identifyUser(OPTED_OUT)).not.toThrow();
    t.track("org_created");
    expect(fetchMock).not.toHaveBeenCalled(); // in-memory opt-out still holds
    getItem.mockRestore();
    setItem.mockRestore();
  });
});
