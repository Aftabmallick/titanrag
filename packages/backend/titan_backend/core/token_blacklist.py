import time
from typing import Any

import structlog

from titan_backend.clients.redis_client import get_redis_client

logger = structlog.get_logger("titanrag.token_blacklist")

REVOCATION_PREFIX = "token_blacklist:"


async def revoke_token(jti: str, exp: int) -> None:
    """
    Store the token's JTI in Redis until its expiration time.
    """
    now = int(time.time())
    ttl = exp - now
    if ttl <= 0:
        return

    try:
        redis = await get_redis_client()
        await redis.set(f"{REVOCATION_PREFIX}{jti}", "revoked", ex=ttl)
        logger.info("token_revoked", jti=jti, ttl=ttl)
    except Exception as e:
        logger.error("token_revocation_failed", jti=jti, error=str(e))


async def is_token_revoked(jti: str) -> bool:
    """
    Check if a token's JTI is in the revocation blacklist.
    """
    try:
        redis = await get_redis_client()
        val: Any = await redis.get(f"{REVOCATION_PREFIX}{jti}")
        return val is not None
    except Exception as e:
        logger.warning("token_revocation_check_failed", jti=jti, error=str(e))
        return False
