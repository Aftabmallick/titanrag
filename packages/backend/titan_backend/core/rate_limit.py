import time
from collections.abc import Callable
from typing import Any, cast

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.config import settings

logger = structlog.get_logger("titanrag.rate_limit")


class SlidingWindowRateLimiter:
    """
    High-performance Redis sliding window rate limiter using sorted sets.
    """

    @staticmethod
    async def check_rate_limit(
        identifier: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int, int]:
        """
        Returns: (is_allowed, remaining, reset_time_seconds, retry_after)
        """
        now = time.time()
        clear_before = now - window_seconds
        redis_key = f"rate_limit:{identifier}"

        try:
            redis = await get_redis_client()
            pipe = redis.pipeline()
            # Remove timestamps outside current window
            pipe.zremrangebyscore(redis_key, 0, clear_before)
            # Count remaining requests in current window
            pipe.zcard(redis_key)
            results = await pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                # Find oldest entry in window to calculate retry_after
                oldest = await redis.zrange(redis_key, 0, 0, withscores=True)
                retry_after = int(window_seconds - (now - oldest[0][1])) if oldest else 1
                retry_after = max(retry_after, 1)
                return False, 0, int(now + retry_after), retry_after

            # Add current request timestamp
            add_pipe = redis.pipeline()
            add_pipe.zadd(redis_key, {str(now): now})
            add_pipe.expire(redis_key, window_seconds + 5)
            await add_pipe.execute()

            remaining = max(0, limit - (current_count + 1))
            reset_time = int(now + window_seconds)
            return True, remaining, reset_time, 0

        except Exception as e:
            logger.warning("rate_limiter_redis_error", error=str(e), identifier=identifier)
            return True, limit, int(now + window_seconds), 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        if settings.RATE_LIMIT_DISABLED:
            return cast(Response, await call_next(request))

        # Exclude internal health and metrics from rate limits
        path = request.url.path
        if path.startswith("/health") or path == "/metrics" or path.startswith("/docs") or path.startswith("/openapi"):
            return cast(Response, await call_next(request))

        client_ip = request.client.host if request.client else "unknown"
        # Determine user limit or anonymous limit
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")

        import hashlib

        identifier = f"ip:{client_ip}"
        limit = settings.RATE_LIMIT_PER_MINUTE_ANONYMOUS

        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            identifier = f"auth:{token_hash}"
            limit = settings.RATE_LIMIT_PER_MINUTE_MEMBER
        elif api_key_header:
            key_hash = hashlib.sha256(api_key_header.strip().encode("utf-8")).hexdigest()[:16]
            identifier = f"apikey:{key_hash}"
            limit = settings.RATE_LIMIT_PER_MINUTE_MEMBER

        is_allowed, remaining, reset_time, retry_after = await SlidingWindowRateLimiter.check_rate_limit(
            identifier=identifier,
            limit=limit,
            window_seconds=60,
        )

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit of {limit} req/min exceeded. Please retry after {retry_after} seconds.",
                        "details": {"retry_after": retry_after, "limit": limit},
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                },
            )

        response: Response = cast(Response, await call_next(request))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response
