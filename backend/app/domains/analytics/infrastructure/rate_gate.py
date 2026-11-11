"""Redis-backed per-user ingest throttle (IngestRateGate port).

Deliberately not slowapi: the ingest endpoint answers 204 to every
authenticated request, valid or dropped, so a prober gets no oracle and the
fire-and-forget client never sees a 429 toast. Over-limit events are simply
not stored. Fail-open like the other Redis guards — no Redis, no throttle.
"""

import logging
import time
import uuid

from app.core import error_handling

logger = logging.getLogger(__name__)


class RedisIngestRateGate:
    def __init__(self, *, per_minute: int) -> None:
        self.per_minute = per_minute

    async def allow(self, user_id: uuid.UUID) -> bool:
        try:
            redis = error_handling._redis_client()
            key = f"analytics_ingest:{user_id}:{int(time.time() // 60)}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)
            return int(count) <= self.per_minute
        except Exception:
            logger.warning("analytics rate gate skipped: Redis unavailable", exc_info=True)
            return True
