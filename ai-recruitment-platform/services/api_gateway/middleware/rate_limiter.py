"""
Redis-based sliding window rate limiter middleware.
"""

import logging
import os
import time
from typing import Optional, Tuple

import redis.asyncio as aioredis
from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("api-gateway.rate_limiter")

# ── Configuration ─────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Default limits (requests per window_seconds)
DEFAULT_USER_LIMIT = int(os.getenv("RATE_LIMIT_USER", "100"))
DEFAULT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Per-endpoint overrides  { path_prefix: (limit, window_seconds) }
ENDPOINT_LIMITS: dict[str, Tuple[int, int]] = {
    "/api/v1/outreach/send":     (20, 60),    # Outreach sends: 20/min
    "/api/v1/outreach/bulk":     (5, 60),     # Bulk operations: 5/min
    "/api/v1/employers/search":  (200, 60),   # Search: 200/min
    "/api/v1/candidates/match":  (50, 60),    # AI matching: 50/min
    "/api/v1/analytics":         (300, 60),   # Analytics: 300/min
    "/api/v1/auth/login":        (10, 60),    # Login brute-force protection
    "/api/v1/auth/register":     (5, 60),     # Registration
    "/api/v1/auth/forgot":       (3, 300),    # Password reset: 3 per 5 min
}

# Paths exempt from rate limiting
EXEMPT_PATHS = {
    "/health",
    "/metrics",
    "/docs",
    "/api/v1/openapi.json",
    "/api/v1/health",
}

# Redis key prefix
KEY_PREFIX = "rl:"


def _resolve_limit(path: str) -> Tuple[int, int]:
    """Return (limit, window_seconds) for the given path."""
    for prefix, limits in ENDPOINT_LIMITS.items():
        if path.startswith(prefix):
            return limits
    return DEFAULT_USER_LIMIT, DEFAULT_WINDOW_SECONDS


async def _sliding_window_check(
    redis: aioredis.Redis,
    key: str,
    limit: int,
    window: int,
) -> Tuple[bool, int, int]:
    """
    Sliding window rate limit check using Redis sorted sets.

    Returns:
        (allowed, remaining, reset_ts)
    """
    now = time.time()
    window_start = now - window

    pipe = redis.pipeline()
    # Remove timestamps older than the window
    pipe.zremrangebyscore(key, "-inf", window_start)
    # Count remaining in window
    pipe.zcard(key)
    # Add current request timestamp (score = timestamp, member = timestamp+nano)
    member = f"{now:.6f}"
    pipe.zadd(key, {member: now})
    # Set TTL on the key
    pipe.expire(key, window + 1)
    results = await pipe.execute()

    current_count = results[1]  # count BEFORE adding current request

    if current_count >= limit:
        # Determine earliest entry to calculate when window resets
        oldest = await redis.zrange(key, 0, 0, withscores=True)
        if oldest:
            reset_ts = int(oldest[0][1] + window) + 1
        else:
            reset_ts = int(now + window)
        return False, 0, reset_ts

    remaining = limit - current_count - 1
    reset_ts = int(now + window)
    return True, remaining, reset_ts


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter.

    - Identifies callers by: JWT user_id (if authenticated) or IP address.
    - Per-endpoint limits override the default user limit.
    - Returns 429 with Retry-After and X-RateLimit-* headers.
    """

    def __init__(self, app, redis_client: Optional[aioredis.Redis] = None):
        super().__init__(app)
        self._redis: Optional[aioredis.Redis] = redis_client
        self._redis_url = REDIS_URL

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    def _identify_caller(self, request: Request) -> str:
        """Return a stable identifier for the caller."""
        # Prefer authenticated user ID
        user_id: Optional[str] = getattr(getattr(request.state, "user", None), "user_id", None)
        if user_id:
            return f"user:{user_id}"
        # Fall back to IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Exempt certain paths
        if path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        limit, window = _resolve_limit(path)
        caller = self._identify_caller(request)
        # Build a key that combines the caller and endpoint bucket
        # Normalise path to avoid cache busting via query params
        endpoint_key = path.rstrip("/") or "/"
        redis_key = f"{KEY_PREFIX}{caller}:{endpoint_key}"

        try:
            redis = await self._get_redis()
            allowed, remaining, reset_ts = await _sliding_window_check(
                redis, redis_key, limit, window
            )
        except Exception as exc:
            logger.warning("Rate limiter Redis error (failing open): %s", exc)
            # Fail open — allow the request through if Redis is unavailable
            return await call_next(request)

        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_ts),
            "X-RateLimit-Window": str(window),
        }

        if not allowed:
            retry_after = max(1, reset_ts - int(time.time()))
            logger.warning(
                "Rate limit exceeded | caller=%s path=%s limit=%d window=%ds",
                caller,
                path,
                limit,
                window,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "caller": caller,
                    "limit": limit,
                    "window_seconds": window,
                    "retry_after": retry_after,
                },
                headers={**headers, "Retry-After": str(retry_after)},
            )

        response = await call_next(request)

        # Attach rate-limit headers to the response
        for k, v in headers.items():
            response.headers[k] = v

        return response
