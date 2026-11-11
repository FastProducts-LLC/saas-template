"""Redis-backed login-attempt tracker (LoginAttemptTracker port).

Redis being unavailable must be neither a login outage nor an open door for
password guessing, so every operation degrades to a small per-process
in-memory tracker instead of "no lockout". That fallback is weaker than Redis
(counters are per worker process and vanish on restart, so N processes allow
up to N x the attempt budget) but it keeps brute force bounded for the length
of an outage; the slowapi IP limit degrades the same way (app.core.ratelimit).

Keys hold a sha256 of the normalized email, so no PII sits in Redis.
"""

import hashlib
import logging
import time

from app.core import error_handling

logger = logging.getLogger(__name__)


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]


class _MemoryAttempts:
    """Bounded in-process stand-in used only while Redis is unreachable."""

    MAX_KEYS = 10_000

    def __init__(self, *, window_seconds: int, lockout_seconds: int) -> None:
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._fails: dict[str, tuple[int, float]] = {}  # key -> (count, window_expiry)
        self._locks: dict[str, float] = {}  # key -> lock_expiry

    def _evict(self, now: float) -> None:
        self._fails = {k: v for k, v in self._fails.items() if v[1] > now}
        self._locks = {k: v for k, v in self._locks.items() if v > now}
        # Still full of live entries (an attack spraying emails): drop the
        # oldest counters, never the locks.
        while len(self._fails) >= self.MAX_KEYS:
            self._fails.pop(next(iter(self._fails)))

    def lockout_remaining(self, key: str) -> int:
        remaining = self._locks.get(key, 0.0) - time.monotonic()
        return max(int(remaining + 0.999), 0)

    def record_failure(self, key: str) -> int:
        now = time.monotonic()
        count, expiry = self._fails.get(key, (0, 0.0))
        if expiry <= now:
            if len(self._fails) >= self.MAX_KEYS:
                self._evict(now)
            # First failure opens the window; later ones don't extend it.
            count, expiry = 0, now + self.window_seconds
        self._fails[key] = (count + 1, expiry)
        return count + 1

    def lock(self, key: str) -> None:
        now = time.monotonic()
        if len(self._locks) >= self.MAX_KEYS:
            self._evict(now)
        self._locks[key] = now + self.lockout_seconds
        self._fails.pop(key, None)

    def clear(self, key: str) -> None:
        self._fails.pop(key, None)
        self._locks.pop(key, None)


class RedisLoginAttemptTracker:
    def __init__(self, *, window_seconds: int, lockout_seconds: int) -> None:
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._memory = _MemoryAttempts(
            window_seconds=window_seconds, lockout_seconds=lockout_seconds
        )

    def _fails_key(self, key: str) -> str:
        return f"login_lockout:fails:{_key_hash(key)}"

    def _lock_key(self, key: str) -> str:
        return f"login_lockout:lock:{_key_hash(key)}"

    async def lockout_remaining(self, key: str) -> int:
        # A lock taken in memory during an outage stays in force after Redis
        # comes back, so honor whichever is longer.
        local = self._memory.lockout_remaining(_key_hash(key))
        try:
            ttl = await error_handling._redis_client().ttl(self._lock_key(key))
            return max(ttl, local, 0)
        except Exception:
            logger.warning("lockout check: Redis unavailable, using in-memory", exc_info=True)
            return local

    async def record_failure(self, key: str) -> int:
        try:
            redis = error_handling._redis_client()
            fails_key = self._fails_key(key)
            count = await redis.incr(fails_key)
            if count == 1:
                # First failure opens the window; later ones don't extend it,
                # so a slow trickle of failures can't lock an account forever.
                await redis.expire(fails_key, self.window_seconds)
            return int(count)
        except Exception:
            logger.warning("failure count: Redis unavailable, using in-memory", exc_info=True)
            return self._memory.record_failure(_key_hash(key))

    async def lock(self, key: str) -> None:
        try:
            redis = error_handling._redis_client()
            await redis.set(self._lock_key(key), "1", ex=self.lockout_seconds)
            await redis.delete(self._fails_key(key))
        except Exception:
            logger.warning("lock: Redis unavailable, using in-memory", exc_info=True)
            self._memory.lock(_key_hash(key))

    async def clear(self, key: str) -> None:
        self._memory.clear(_key_hash(key))
        try:
            redis = error_handling._redis_client()
            await redis.delete(self._fails_key(key), self._lock_key(key))
        except Exception:
            logger.warning("lockout clear skipped: Redis unavailable", exc_info=True)
