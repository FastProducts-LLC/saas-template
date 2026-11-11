// Test helpers for stubbing the global fetch the api client calls.
//
// client.ts only ever touches a handful of Response members: `ok`, `status`,
// `statusText`, `headers` (a real `Headers` so `.get(...)` works), and one of
// `json()` / `blob()`. jsonResponse / blobResponse build the minimal shape that
// satisfies those reads without pulling in a full Response polyfill.

import { vi } from "vitest";

type FetchMock = ReturnType<typeof vi.fn>;

const realFetch = globalThis.fetch;

/** Swap globalThis.fetch for a vi.fn() and return it for queueing responses. */
export function mockFetch(): FetchMock {
  const fn = vi.fn();
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
}

/** Restore the original global fetch — call from afterEach. */
export function restoreFetch(): void {
  globalThis.fetch = realFetch;
}

interface ResponseInitLike {
  headers?: Record<string, string>;
}

/** A Response-compatible object whose json() yields `body`. */
export function jsonResponse(
  status: number,
  body: unknown = {},
  init: ResponseInitLike = {},
): Response {
  const headers = new Headers(init.headers);
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: statusTextFor(status),
    headers,
    json: async () => body,
    blob: async () => new Blob([JSON.stringify(body)], { type: "application/json" }),
  } as unknown as Response;
}

/** A Response-compatible object whose blob() yields `blob` (for apiBlob). */
export function blobResponse(
  status: number,
  blob: Blob = new Blob(["binary"]),
  init: ResponseInitLike = {},
): Response {
  const headers = new Headers(init.headers);
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: statusTextFor(status),
    headers,
    json: async () => ({}),
    blob: async () => blob,
  } as unknown as Response;
}

function statusTextFor(status: number): string {
  const map: Record<number, string> = {
    200: "OK",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    404: "Not Found",
    409: "Conflict",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
  };
  return map[status] ?? "";
}
