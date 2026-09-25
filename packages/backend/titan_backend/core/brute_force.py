import asyncio
import time
from typing import Any

import structlog

from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException

logger = structlog.get_logger("titanrag.brute_force")

MAX_ATTEMPTS = settings.LOGIN_MAX_ATTEMPTS
LOCKOUT_DURATION_SECONDS = settings.LOGIN_LOCKOUT_DURATION_SECONDS
FAILURE_PREFIX = "login_failures:"
LOCKOUT_PREFIX = "account_locked:"


async def record_login_failure(email: str) -> tuple[int, bool, int]:
    """
    Records a failed login attempt for the given email.
    Returns: (attempt_count, is_locked, retry_after)
    """
    clean_email = email.strip().lower()
    try:
        redis = await get_redis_client()
        attempts = await redis.incr(f"{FAILURE_PREFIX}{clean_email}")
        if attempts == 1:
            await redis.expire(f"{FAILURE_PREFIX}{clean_email}", LOCKOUT_DURATION_SECONDS)

        if attempts >= MAX_ATTEMPTS:
            # Set lockout key
            await redis.set(
                f"{LOCKOUT_PREFIX}{clean_email}",
                int(time.time()) + LOCKOUT_DURATION_SECONDS,
                ex=LOCKOUT_DURATION_SECONDS,
            )
            logger.warning("account_locked_out", email=clean_email, attempts=attempts)
            return attempts, True, LOCKOUT_DURATION_SECONDS

        # Progressive delay backoff: 2^(attempt - 1) capped at 30 seconds
        delay = min(2 ** (attempts - 1), 30)
        if delay > 0:
            await asyncio.sleep(delay)

        return attempts, False, 0
    except Exception as e:
        logger.warning("record_login_failure_error", email=clean_email, error=str(e))
        return 1, False, 0


async def check_account_locked(email: str) -> tuple[bool, int]:
    """
    Check if the account is currently locked out.
    Returns: (is_locked, retry_after_seconds)
    """
    clean_email = email.strip().lower()
    try:
        redis = await get_redis_client()
        lock_until: Any = await redis.get(f"{LOCKOUT_PREFIX}{clean_email}")
        if lock_until:
            retry_after = max(int(lock_until) - int(time.time()), 1)
            return True, retry_after
        return False, 0
    except Exception as e:
        logger.warning("check_account_locked_error", email=clean_email, error=str(e))
        return False, 0


async def clear_login_failures(email: str) -> None:
    """
    Clear failed login count and lockout on successful authentication.
    """
    clean_email = email.strip().lower()
    try:
        redis = await get_redis_client()
        await redis.delete(f"{FAILURE_PREFIX}{clean_email}")
        await redis.delete(f"{LOCKOUT_PREFIX}{clean_email}")
    except Exception as e:
        logger.warning("clear_login_failures_error", email=clean_email, error=str(e))


def raise_if_locked(is_locked: bool, retry_after: int) -> None:
    if is_locked:
        raise AppException(
            message=f"Account is temporarily locked due to excessive failed login attempts. Please try again in {retry_after} seconds.",
            status_code=423,
            error_code="ACCOUNT_LOCKED",
            details={"retry_after": retry_after},
        )
