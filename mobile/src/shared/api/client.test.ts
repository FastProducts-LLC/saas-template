// Unit tests for the native API client: auth header wiring, body-based
// refresh with rotation, single-flight, idempotency keys, and ApiError
// normalization. Pure Node — platform adapters are injected fakes.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  ApiError,
  configureApi,
  setAccessToken,
  tryRefresh,
  type RefreshTokenStore,
} from "./client";
import { subscribeErrors } from "./errorBus";

function makeTokenStore(initial: string | null = null) {
  let value = initial;
  const store: RefreshTokenStore = {
    get: vi.fn(async () => value),
    set: vi.fn(async (t: string | null) => {
      value = t;
    }),
  };
  return { store, current: () => value };
}

function jsonResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  setAccessToken(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function configure(store: RefreshTokenStore, onSessionExpired?: () => void) {
  configureApi({
    baseUrl: "http://test/api",
    refreshTokens: store,
    randomUUID: () => "fixed-uuid",
    onSessionExpired,
  });
}

describe("api()", () => {
  it("attaches bearer token, X-Client and Content-Type", async () => {
    const { store } = makeTokenStore();
    configure(store);
    setAccessToken("access-1");
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await api("/orgs", { method: "POST", body: JSON.stringify({ a: 1 }) });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://test/api/orgs");
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer access-1");
    expect(headers.get("X-Client")).toBe("mobile");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Idempotency-Key")).toBe("fixed-uuid");
  });

  it("does not add an Idempotency-Key to GETs", async () => {
    const { store } = makeTokenStore();
    configure(store);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, []));

    await api("/orgs");

    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Idempotency-Key")).toBeNull();
  });

  it("refreshes once on 401, persists the rotated token, and retries with the SAME idempotency key", async () => {
    const { store, current } = makeTokenStore("refresh-old");
    configure(store);
    setAccessToken("stale");

    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { code: "ERR_AUTH_003" })) // original
      .mockResolvedValueOnce(
        jsonResponse(200, {
          access_token: "access-2",
          refresh_token: "refresh-new",
        }),
      ) // refresh
      .mockResolvedValueOnce(jsonResponse(201, { id: "g1" })); // retry

    const result = await api<{ id: string }>("/orgs/o1/generations", {
      method: "POST",
      body: JSON.stringify({ kind: "image_gpt", prompt: "x" }),
    });

    expect(result.id).toBe("g1");
    expect(current()).toBe("refresh-new");

    const refreshCall = fetchMock.mock.calls[1];
    expect(refreshCall[0]).toBe("http://test/api/auth/refresh");
    expect(JSON.parse(refreshCall[1].body)).toEqual({
      refresh_token: "refresh-old",
    });

    const firstKey = new Headers(fetchMock.mock.calls[0][1].headers).get(
      "Idempotency-Key",
    );
    const retryKey = new Headers(fetchMock.mock.calls[2][1].headers).get(
      "Idempotency-Key",
    );
    expect(firstKey).toBe("fixed-uuid");
    expect(retryKey).toBe(firstKey);

    const retryAuth = new Headers(fetchMock.mock.calls[2][1].headers).get(
      "Authorization",
    );
    expect(retryAuth).toBe("Bearer access-2");
  });

  it("wipes the session and notifies when the refresh token is rejected", async () => {
    const onSessionExpired = vi.fn();
    const { store, current } = makeTokenStore("refresh-dead");
    configure(store, onSessionExpired);
    setAccessToken("had-a-session");

    const published: ApiError[] = [];
    const unsubscribe = subscribeErrors((e) => published.push(e));

    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { code: "ERR_AUTH_003" })) // original
      .mockResolvedValueOnce(jsonResponse(401, { code: "ERR_AUTH_002" })); // refresh rejected

    await expect(api("/orgs")).rejects.toBeInstanceOf(ApiError);

    expect(current()).toBeNull();
    expect(onSessionExpired).toHaveBeenCalledOnce();
    expect(published.some((e) => e.code === "ERR_AUTH_002")).toBe(true);
    unsubscribe();
  });

  it("keeps the refresh token on transient refresh failures (5xx)", async () => {
    const { store, current } = makeTokenStore("refresh-keep");
    configure(store);
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 503 }));

    expect(await tryRefresh()).toBe(false);
    expect(current()).toBe("refresh-keep");
  });

  it("single-flights concurrent refreshes", async () => {
    const { store } = makeTokenStore("refresh-1");
    configure(store);

    let resolveRefresh!: (r: Response) => void;
    fetchMock.mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveRefresh = resolve;
      }),
    );

    const a = tryRefresh();
    const b = tryRefresh();
    resolveRefresh(
      jsonResponse(200, { access_token: "a2", refresh_token: "refresh-2" }),
    );

    expect(await Promise.all([a, b])).toEqual([true, true]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("normalizes problem+json into a catalog-aware ApiError", async () => {
    const { store } = makeTokenStore();
    configure(store);
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        code: "ERR_VAL_001",
        detail: "Validation failed.",
        instance: "abc123",
        fields: { email: "Enter a valid email address." },
      }),
    );

    const error = (await api("/auth/register", {
      method: "POST",
      body: "{}",
    }).catch((e) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("ERR_VAL_001");
    expect(error.errorId).toBe("abc123");
    expect(error.fields.email).toMatch(/valid email/);
    expect(error.reference).toBe("ERR_VAL_001 · abc123");
    expect(error.userMessage.length).toBeGreaterThan(0);
  });

  it("falls back to a status-mapped code for bodyless failures", async () => {
    const { store } = makeTokenStore();
    configure(store);
    fetchMock.mockResolvedValueOnce(
      new Response("Bad Gateway", { status: 502 }),
    );

    const error = (await api("/orgs").catch((e) => e)) as ApiError;
    expect(error.code).toBe("ERR_SRV_002");
  });

  it("fills param-specific copy only when every param is present", async () => {
    configure(makeTokenStore().store);
    fetchMock.mockResolvedValueOnce(
      jsonResponse(403, {
        code: "ERR_ENT_002",
        params: { limit: 5, resource: "seats" },
      }),
    );
    const full = (await api("/orgs/x/invitations", { method: "POST" }).catch(
      (e) => e,
    )) as ApiError;
    expect(full.userMessage).toBe(
      "Your organization has reached its plan limit of 5 seats.",
    );

    fetchMock.mockResolvedValueOnce(
      jsonResponse(403, { code: "ERR_ENT_002", params: { limit: 5 } }),
    );
    const partial = (await api("/orgs/x/invitations", { method: "POST" }).catch(
      (e) => e,
    )) as ApiError;
    expect(partial.userMessage).toBe(
      "Your organization has reached its plan limit.",
    );
  });

  it("keeps an unknown code for support but shows the status copy", async () => {
    configure(makeTokenStore().store);
    fetchMock.mockResolvedValueOnce(
      jsonResponse(409, {
        code: "ERR_NEW_001",
        detail: "dev text",
        retryable: false,
      }),
    );
    const error = (await api("/x").catch((e) => e)) as ApiError;
    expect(error.code).toBe("ERR_NEW_001");
    expect(error.userMessage).not.toContain("dev text");
    expect(error.retryable).toBe(false);
  });

  it("never refreshes for /auth/ paths", async () => {
    const { store } = makeTokenStore("refresh-x");
    configure(store);
    fetchMock.mockResolvedValueOnce(
      jsonResponse(401, { code: "ERR_AUTH_001" }),
    );

    await expect(
      api("/auth/login", { method: "POST", body: "{}" }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1); // no refresh attempt
  });
});
