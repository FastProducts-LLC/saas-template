// Tiny pub/sub connecting the API client / query caches (non-React code) to
// the error UI (React). client.ts publishes every ApiError it throws; the
// ErrorUIProvider subscribes and routes by the catalog's `display` field.

import type { ApiError } from "./client";

type Handler = (err: ApiError) => void;

const handlers = new Set<Handler>();

export function publishError(err: unknown): void {
  // Only catalog-aware errors flow through the bus; anything else is the
  // caller's problem (and usually a bug to surface in dev tools, not a toast).
  if (!isApiError(err)) return;
  for (const handler of handlers) handler(err);
}

export function subscribeErrors(handler: Handler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

function isApiError(err: unknown): err is ApiError {
  return err instanceof Error && "code" in err && "status" in err;
}
