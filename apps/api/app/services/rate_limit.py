"""Fixed-window rate limiting for brute-force-sensitive endpoints.

`InMemoryRateLimiter` is correct and tested, but is per-process state —
fine for this single-process development environment, wrong for a
multi-instance deployment where each instance would enforce its own
separate limit. `RedisRateLimiter` is the real, shared-state
implementation for that case; it has not been exercised against a live
Redis instance in this environment (no Docker here — see
docs/architecture/phase-1-foundation.md), the same honest gap as every
other Redis-dependent code path in this codebase. `FORGE_RATE_LIMIT_BACKEND`
selects which one `get_rate_limiter()` constructs.
"""

import time
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class RateLimiter(Protocol):
    async def check(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        """Return True if this request is allowed, False if the caller has
        exceeded `max_requests` within the trailing `window_seconds`."""
        ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    async def check(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        window_start = now - window_seconds
        hits = [t for t in self._hits.get(key, []) if t > window_start]
        if len(hits) >= max_requests:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True


class RedisRateLimiter:
    """Fixed-window counter via INCR + EXPIRE. Not exercised against a
    live Redis instance in this environment — see module docstring."""

    def __init__(self, redis_url: str) -> None:
        from redis.asyncio import Redis

        self._redis = Redis.from_url(redis_url)

    async def check(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        redis_key = f"forge:ratelimit:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        return count <= max_requests


@lru_cache
def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    if settings.rate_limit_backend == "redis":
        return RedisRateLimiter(settings.redis_url)
    return InMemoryRateLimiter()
