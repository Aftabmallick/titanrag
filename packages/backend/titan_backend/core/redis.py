"""Redis client compatibility module forwarding to titan_backend.clients.redis_client."""

import redis

from titan_backend.clients.redis_client import get_redis, get_redis_client, get_redis_pool
from titan_backend.core.config import settings


def get_redis_client_sync() -> redis.Redis:
    """Return a synchronous Redis client instance."""
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


__all__ = [
    "get_redis",
    "get_redis_client",
    "get_redis_client_sync",
    "get_redis_pool",
]
