"""Idempotency-Key support for mutating requests (Redis-backed).

The frontend api client attaches an `Idempotency-Key` header to every
POST/PUT/PATCH/DELETE and reuses it when it retries — so a retried
timed-out checkout can't double-charge (the catalog's ERR_SRV_002 promise).

Protocol per (key, method, path, caller):
- first request:    marked in-flight, executed; a 2xx response body is
                    cached for IDEMPOTENCY_TTL_SECONDS, non-2xx clears the
                    marker so the client may retry fresh.
- concurrent dupe:  409 ERR_SRV_004 ("still working on your previous attempt").
- later replay:     the cached response, flagged with `Idempotency-Replayed: true`.

The cache key is scoped to a *stable caller identity* so one user can never
replay another user's response by guessing their key. We derive that identity
from the JWT `sub` claim (decoded with the same secret/logic the auth deps
use) rather than the raw Authorization header: the frontend reuses one
Idempotency-Key across its 401-refresh retry (see frontend/src/shared/api/
client.ts), so the retry arrives bearing a *different* access token for the
*same* user. Hashing the raw header would change the fingerprint and the
retry would RE-EXECUTE instead of replay — re-running (and potentially
double-charging) the very call idempotency exists to protect. Keying on `sub`
keeps the fingerprint stable across the refresh.

Tokens that fail signature verification or are missing/malformed fall back to
the raw header value: unauthenticated or garbage requests still get a scoped
fingerprint (so distinct callers don't collide) without trusting an unverified
token's contents.

Redis being unavailable degrades to pass-through (no dedupe, never an outage).
"""

import hashlib
import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core import error_handling
from app.core.security import decode_access_token

logger = logging.getLogger("app.errors")

IDEMPOTENCY_TTL_SECONDS = 24 * 3600
IN_FLIGHT_TTL_SECONDS = 60
MAX_CACHED_BODY_BYTES = 64 * 1024
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXCLUDED_PATHS = {"/api/billing/webhook"}  # Stripe signs + retries on its own
IN_FLIGHT = "__in_flight__"


def _caller_identity(authorization: str) -> str:
    """Stable per-caller identity for the fingerprint.

    Returns the verified JWT `sub` (so a token-refresh retry stays the same
    caller), falling back to the raw header for unauthenticated/garbage
    requests — see the module docstring for why.
    """
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        user_id = decode_access_token(token)
        if user_id is not None:
            return f"sub:{user_id}"
    return f"hdr:{authorization}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        key = request.headers.get("Idempotency-Key")
        if not key or request.method not in MUTATING_METHODS or request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        identity = _caller_identity(request.headers.get("Authorization", ""))
        fingerprint = hashlib.sha256(
            "\x00".join([key, request.method, request.url.path, identity]).encode()
        ).hexdigest()
        redis_key = f"idem:{fingerprint}"
        redis = error_handling._redis_client()

        try:
            acquired = await redis.set(redis_key, IN_FLIGHT, nx=True, ex=IN_FLIGHT_TTL_SECONDS)
            if not acquired:
                cached = await redis.get(redis_key)
                if cached == IN_FLIGHT:
                    return error_handling.problem_response(request, "ERR_SRV_004")
                if cached:
                    stored = json.loads(cached)
                    return Response(
                        content=stored["body"],
                        status_code=stored["status"],
                        media_type=stored["media_type"],
                        headers={"Idempotency-Replayed": "true"},
                    )
        except Exception:
            logger.warning("idempotency store unavailable; passing through")
            return await call_next(request)

        response = await call_next(request)

        if not (200 <= response.status_code < 300):
            # Failed attempts don't burn the key — the client may retry fresh.
            try:
                await redis.delete(redis_key)
            except Exception:
                logger.warning("idempotency store unavailable after response")
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            if len(body) <= MAX_CACHED_BODY_BYTES:
                await redis.set(
                    redis_key,
                    json.dumps(
                        {
                            "status": response.status_code,
                            "body": body.decode("utf-8", errors="replace"),
                            "media_type": response.headers.get("content-type"),
                        }
                    ),
                    ex=IDEMPOTENCY_TTL_SECONDS,
                )
            else:
                await redis.delete(redis_key)
        except Exception:
            logger.warning("idempotency store unavailable after response")
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
