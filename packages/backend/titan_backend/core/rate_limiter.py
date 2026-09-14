import asyncio
import time

import structlog

from titan_backend.clients.redis_client import get_redis_client

logger = structlog.get_logger("titanrag.provider_rate_limiter")


class ProviderTokenBucketLimiter:
    """
    Redis token-bucket rate limiter for external LLM & Embedding providers.
    Enforces RPM (requests per minute) and TPM (tokens per minute) limits.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "text-embedding-3-small",
        max_rpm: int = 3000,
        max_tpm: int = 1_000_000,
    ):
        self.provider = provider
        self.model = model
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm

    def _get_keys(self) -> tuple[str, str]:
        minute_bucket = int(time.time() // 60)
        rpm_key = f"rate:provider:{self.provider}:{self.model}:rpm:{minute_bucket}"
        tpm_key = f"rate:provider:{self.provider}:{self.model}:tpm:{minute_bucket}"
        return rpm_key, tpm_key

    async def acquire(self, estimated_tokens: int = 100, wait: bool = True, max_wait_seconds: float = 10.0) -> bool:
        start_time = time.time()
        while True:
            rpm_key, tpm_key = self._get_keys()
            try:
                redis = await get_redis_client()
                pipe = redis.pipeline()
                pipe.incr(rpm_key)
                pipe.incrby(tpm_key, estimated_tokens)
                pipe.expire(rpm_key, 120)
                pipe.expire(tpm_key, 120)
                results = await pipe.execute()

                current_rpm = results[0]
                current_tpm = results[1]

                if current_rpm <= self.max_rpm and current_tpm <= self.max_tpm:
                    return True

                # Over limit
                if not wait or (time.time() - start_time) >= max_wait_seconds:
                    logger.warning(
                        "provider_rate_limit_exceeded",
                        provider=self.provider,
                        model=self.model,
                        current_rpm=current_rpm,
                        current_tpm=current_tpm,
                    )
                    return False

                # Calculate remaining seconds in this minute window
                sleep_seconds = 60.0 - (time.time() % 60.0) + 0.1
                sleep_seconds = min(sleep_seconds, max_wait_seconds - (time.time() - start_time))
                if sleep_seconds <= 0:
                    return False

                logger.info("provider_rate_limit_throttling", provider=self.provider, sleep=sleep_seconds)
                await asyncio.sleep(sleep_seconds)

            except Exception as e:
                logger.warning("provider_rate_limiter_redis_error", error=str(e))
                return True
