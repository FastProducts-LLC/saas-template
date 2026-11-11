import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, apiBlob, ApiError, setAccessToken } from "./client";
import { subscribeErrors } from "./errorBus";
import { blobResponse, jsonResponse, mockFetch, restoreFetch } from "../../test/fetchMock";

// The client keeps module-level state (the access token + an in-flight refresh
// promise). The token is reset via the exported setAccessToken(null); the
// refresh promise self-clears in a finally, so resetting the token between
// tests is enough to keep the api()/apiBlob() suites isolated.
beforeEach(() => {
  setAccessToken(null);
  sessionStorage.clear();
});

afterEach(() => {
  restoreFetch();
  setAccessToken(null);
  vi.useRealTimers();
  vi.restoreAllMocks();
});

/** Collect every ApiError published on the bus during a test. */
function captureBus(): { errors: ApiError[]; unsubscribe: () => void } {
  const errors: ApiError[] = [];
  const unsubscribe = subscribeErrors((err) => errors.push(err));
  return { errors, unsubscribe };
}

// ===========================================================================
// Auth headers
// ===========================================================================
describe("api() — auth headers", () => {
  it("attaches an Authorization header after setAccessToken", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, { ok: true }));
    setAccessToken("tok-123");

    await api("/me");

    const headers = fetch.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok-123");
  });

  it("omits the Authorization header without a token", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, { ok: true }));

    await api("/me");

    const headers = fetch.mock.calls[0][1].headers as Headers;
    expect(headers.has("Authorization")).toBe(false);
  });

  it("sets Content-Type for JSON bodies", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, { ok: true }));

    await api("/things", { method: "POST", body: JSON.stringify({ a: 1 }) });

    const headers = fetch.mock.calls[0][1].headers as Headers;
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("calls the proxied /api-prefixed URL", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, {}));

    await api("/me");

    expect(fetch.mock.calls[0][0]).toBe("/api/me");
  });
});

// ===========================================================================
// Success shapes
// ===========================================================================
describe("api() — success shapes", () => {
  it("resolves the parsed JSON body on 200", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, { id: 7 }));

    await expect(api("/things/7")).resolves.toEqual({ id: 7 });
  });

  it("resolves undefined on 204", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(204));

    await expect(api("/things/7", { method: "DELETE" })).resolves.toBeUndefined();
  });
});

// ===========================================================================
// 401 → refresh → retry once
// ===========================================================================
describe("api() — 401 refresh flow", () => {
  it("refreshes once and retries the original request with the new token", async () => {
    const fetch = mockFetch();
    setAccessToken("stale");
    fetch
      // 1) original request → 401
      .mockResolvedValueOnce(jsonResponse(401, { code: "ERR_AUTH_003" }))
      // 2) POST /api/auth/refresh → new token
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "fresh" }))
      // 3) retried original request → success
      .mockResolvedValueOnce(jsonResponse(200, { id: 1 }));

    await expect(api("/me")).resolves.toEqual({ id: 1 });

    expect(fetch).toHaveBeenCalledTimes(3);
    // Refresh hits the exact endpoint with POST + credentials.
    expect(fetch.mock.calls[1][0]).toBe("/api/auth/refresh");
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: "POST", credentials: "include" });
    // Retry carries the refreshed token.
    const retryHeaders = fetch.mock.calls[2][1].headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
  });

  it("does NOT refresh when the 401 came from an /auth/ path", async () => {
    const fetch = mockFetch();
    setAccessToken("tok");
    fetch.mockResolvedValue(jsonResponse(401, { code: "ERR_AUTH_001" }));

    await expect(api("/auth/login", { method: "POST" })).rejects.toBeInstanceOf(ApiError);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe("/api/auth/login");
  });

  it("clears the token and publishes a session-expired error when refresh fails", async () => {
    const fetch = mockFetch();
    const { errors, unsubscribe } = captureBus();
    setAccessToken("stale");
    fetch
      // original → 401
      .mockResolvedValueOnce(jsonResponse(401, { code: "ERR_AUTH_003" }))
      // refresh → 401 (failed)
      .mockResolvedValueOnce(jsonResponse(401, {}));

    await expect(api("/me")).rejects.toBeInstanceOf(ApiError);
    unsubscribe();

    // A failed refresh that HAD a session publishes ERR_AUTH_002.
    expect(errors.some((e) => e.code === "ERR_AUTH_002")).toBe(true);
    expect(sessionStorage.getItem("sessionExpired")).toBe("1");

    // Token was cleared: a follow-up request carries no Authorization header.
    fetch.mockResolvedValueOnce(jsonResponse(200, {}));
    await api("/ping");
    const lastHeaders = fetch.mock.calls.at(-1)?.[1].headers as Headers;
    expect(lastHeaders.has("Authorization")).toBe(false);
  });
});

// ===========================================================================
// Idempotency-Key
// ===========================================================================
describe("api() — Idempotency-Key", () => {
  it("attaches an Idempotency-Key to mutating requests", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, {}));

    await api("/things", { method: "POST", body: "{}" });

    const headers = fetch.mock.calls[0][1].headers as Headers;
    expect(headers.get("Idempotency-Key")).toBeTruthy();
  });

  it("does not attach an Idempotency-Key to GET requests", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(200, {}));

    await api("/things");

    const headers = fetch.mock.calls[0][1].headers as Headers;
    expect(headers.has("Idempotency-Key")).toBe(false);
  });

  it("reuses the SAME Idempotency-Key across catalog-retry attempts", async () => {
    vi.useFakeTimers();
    const fetch = mockFetch();
    fetch
      // ERR_BILL_002 has retry { afterMs: 2000, max: 2 }.
      .mockResolvedValueOnce(jsonResponse(502, { code: "ERR_BILL_002" }))
      .mockResolvedValueOnce(jsonResponse(502, { code: "ERR_BILL_002" }))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const promise = api("/billing/checkout", { method: "POST", body: "{}" });
    await vi.advanceTimersByTimeAsync(10000);
    await expect(promise).resolves.toEqual({ ok: true });

    const keyOf = (i: number) => (fetch.mock.calls[i][1].headers as Headers).get("Idempotency-Key");
    const key = keyOf(0);
    expect(key).toBeTruthy();
    expect(keyOf(1)).toBe(key);
    expect(keyOf(2)).toBe(key);
  });
});

// ===========================================================================
// Catalog-driven retry
// ===========================================================================
describe("api() — catalog-driven retry", () => {
  it("retries a mutation retry.max times then succeeds", async () => {
    vi.useFakeTimers();
    const fetch = mockFetch();
    // ERR_SRV_002: retry { afterMs: 2000, max: 2 } → up to 2 retries.
    fetch
      .mockResolvedValueOnce(jsonResponse(504, { code: "ERR_SRV_002" }))
      .mockResolvedValueOnce(jsonResponse(504, { code: "ERR_SRV_002" }))
      .mockResolvedValueOnce(jsonResponse(200, { done: true }));

    const promise = api("/jobs", { method: "POST", body: "{}" });
    await vi.advanceTimersByTimeAsync(10000);

    await expect(promise).resolves.toEqual({ done: true });
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("gives up after retry.max retries and throws", async () => {
    vi.useFakeTimers();
    const fetch = mockFetch();
    const { errors, unsubscribe } = captureBus();
    fetch.mockResolvedValue(jsonResponse(504, { code: "ERR_SRV_002" }));

    const promise = api("/jobs", { method: "POST", body: "{}" });
    const assertion = expect(promise).rejects.toMatchObject({ code: "ERR_SRV_002" });
    await vi.advanceTimersByTimeAsync(10000);
    await assertion;
    unsubscribe();

    // 1 original + 2 retries (max).
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(errors.some((e) => e.code === "ERR_SRV_002")).toBe(true);
  });

  it("does NOT run the retry loop for GET requests", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(504, { code: "ERR_SRV_002" }));

    await expect(api("/jobs")).rejects.toMatchObject({ code: "ERR_SRV_002" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

// ===========================================================================
// Error normalization
// ===========================================================================
describe("api() — error normalization", () => {
  it("maps an unmodeled status with no body code via STATUS_FALLBACK", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(404, {}));

    await expect(api("/missing")).rejects.toMatchObject({
      status: 404,
      code: "ERR_REQ_002",
    });
  });

  it("exposes userMessage / severity / reference from the catalog", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(409, { code: "ERR_CRD_001", instance: "abc123" }));

    const err = await api("/credits/spend", { method: "POST", body: "{}" }).catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as ApiError;
    expect(apiErr.code).toBe("ERR_CRD_001");
    expect(apiErr.userMessage).toBe("Your organization doesn't have enough credits for this.");
    expect(apiErr.severity).toBe("info");
    expect(apiErr.reference).toBe("ERR_CRD_001 · abc123");
  });

  it("falls back to ERR_REQ_001 for an unknown body code on a status with no fallback", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(418, { code: "NOT_A_REAL_CODE" }));

    await expect(api("/teapot")).rejects.toMatchObject({ status: 418, code: "ERR_REQ_001" });
  });

  it("fills the specific catalog copy from server params", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(
      jsonResponse(409, { code: "ERR_CRD_001", params: { required: 1200, available: 3 } }),
    );
    const err = (await api("/x", { method: "POST" }).catch((e: unknown) => e)) as ApiError;
    expect(err.params).toEqual({ required: 1200, available: 3 });
    expect(err.userMessage).toBe(
      `This needs ${(1200).toLocaleString()} credits, but your organization has 3.`,
    );
  });

  it("falls back to the generic copy when any param is missing", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(jsonResponse(409, { code: "ERR_CRD_001", params: { required: 5 } }));
    const err = (await api("/x", { method: "POST" }).catch((e: unknown) => e)) as ApiError;
    expect(err.userMessage).toBe("Your organization doesn't have enough credits for this.");
    expect(err.userMessage).not.toContain("{");
  });

  it("keeps a code newer than this bundle but uses the status copy", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(
      jsonResponse(403, { code: "ERR_NEW_001", detail: "dev-only text", instance: "r1" }),
    );
    const err = (await api("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("ERR_NEW_001");
    expect(err.reference).toBe("ERR_NEW_001 · r1");
    expect(err.userMessage).toBe("You don't have permission to do that in this organization.");
    expect(err.userMessage).not.toContain("dev-only");
  });

  it("reads retryable / retry_after_ms from the envelope", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(
      jsonResponse(429, { code: "ERR_REQ_004", retryable: true, retry_after_ms: 4000 }),
    );
    const before = Date.now();
    const err = (await api("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.retryable).toBe(true);
    expect(err.retryAt).toBeGreaterThanOrEqual(before + 4000);
  });

  it("ignores a malformed params/fields payload", async () => {
    const fetch = mockFetch();
    fetch.mockResolvedValue(
      jsonResponse(409, { code: "ERR_CRD_001", params: ["nope"], fields: "nope" }),
    );
    const err = (await api("/x", { method: "POST" }).catch((e: unknown) => e)) as ApiError;
    expect(err.params).toEqual({});
    expect(err.fields).toEqual({});
  });

  it("maps a network rejection (TypeError) to ERR_NET_001", async () => {
    const fetch = mockFetch();
    fetch.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api("/me")).rejects.toMatchObject({ status: 0, code: "ERR_NET_001" });
  });
});

// ===========================================================================
// apiBlob
// ===========================================================================
describe("apiBlob()", () => {
  it("returns the blob on success", async () => {
    const fetch = mockFetch();
    const payload = new Blob(["image-bytes"]);
    fetch.mockResolvedValue(blobResponse(200, payload));

    await expect(apiBlob("/media/1")).resolves.toBe(payload);
  });

  it("refreshes on 401 then retries and returns the blob", async () => {
    const fetch = mockFetch();
    setAccessToken("stale");
    const payload = new Blob(["image-bytes"]);
    fetch
      .mockResolvedValueOnce(blobResponse(401))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "fresh" }))
      .mockResolvedValueOnce(blobResponse(200, payload));

    await expect(apiBlob("/media/1")).resolves.toBe(payload);

    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls[1][0]).toBe("/api/auth/refresh");
    const retryHeaders = fetch.mock.calls[2][1].headers as Headers;
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
  });

  it("publishes and throws an ApiError on a non-ok response", async () => {
    const fetch = mockFetch();
    const { errors, unsubscribe } = captureBus();
    fetch.mockResolvedValue(blobResponse(404));

    await expect(apiBlob("/media/1")).rejects.toMatchObject({ status: 404, code: "ERR_REQ_002" });
    unsubscribe();
    expect(errors.some((e) => e.code === "ERR_REQ_002")).toBe(true);
  });
});

// ===========================================================================
// Single-flight refresh — concurrent 401s must share ONE /api/auth/refresh
// call (rotating refresh tokens would log the user out otherwise). These use
// resetModules + dynamic import for a pristine module each time.
// ===========================================================================
async function loadClient() {
  vi.resetModules();
  return await import("./client");
}

function refreshResponse() {
  return new Response(JSON.stringify({ access_token: "tok" }), { status: 200 });
}

describe("tryRefresh", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shares one in-flight refresh across concurrent callers", async () => {
    const client = await loadClient();
    let resolveRefresh!: (r: Response) => void;
    const fetchMock = vi
      .fn()
      .mockImplementation(() => new Promise<Response>((resolve) => (resolveRefresh = resolve)));
    vi.stubGlobal("fetch", fetchMock);

    const first = client.tryRefresh();
    const second = client.tryRefresh();

    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveRefresh(refreshResponse());
    await expect(first).resolves.toBe(true);
    await expect(second).resolves.toBe(true);
  });

  it("starts a new refresh once the previous one settles", async () => {
    const client = await loadClient();
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(refreshResponse()));
    vi.stubGlobal("fetch", fetchMock);

    await client.tryRefresh();
    await client.tryRefresh();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("returns false (for every waiter) when the refresh fails", async () => {
    const client = await loadClient();
    const fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response(null, { status: 401 })));
    vi.stubGlobal("fetch", fetchMock);

    const [first, second] = await Promise.all([client.tryRefresh(), client.tryRefresh()]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(first).toBe(false);
    expect(second).toBe(false);
  });
});
