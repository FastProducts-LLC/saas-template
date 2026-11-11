"""Shared rate limiter, backed by the Redis instance the stack already runs.

Used to throttle abuse-prone endpoints (auth). The limiter keys on client IP,
so in production run uvicorn with `--forwarded-allow-ips` (and a trusted proxy
setting `X-Forwarded-For`) or the key collapses to the proxy's address.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# headers_enabled is required for _inject_headers to emit X-RateLimit-* and
# Retry-After on 429s — the frontend's retry countdown depends on Retry-After.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    headers_enabled=True,
    # Redis down must not mean "no limits" (or 500s on every limited route):
    # fall back to per-process in-memory counters until it recovers.
    in_memory_fallback_enabled=True,
)
