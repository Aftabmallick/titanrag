import time
from uuid import UUID

import structlog
from titan_backend.clients.redis_client import get_redis

logger = structlog.get_logger(__name__)


class PluginCircuitBreaker:
    """
    Redis-backed circuit breaker for external micro-hook plugins with local in-memory fallback.
    Protects the TitanRAG pipeline from misbehaving, crashing, or timing-out external webhooks.
    """

    FAILURE_THRESHOLD = 5
    COOLDOWN_SECONDS = 60

    # Local fallback cache in case Redis is disconnected or during standalone unit tests
    _local_failures: dict[str, int] = {}
    _local_tripped_at: dict[str, float] = {}

    @classmethod
    def _key_base(cls, plugin_id: UUID | str) -> str:
        return f"plugin:cb:{plugin_id}"

    @classmethod
    async def can_execute(cls, plugin_id: UUID | str) -> bool:
        """
        Check if an outgoing webhook request can be dispatched.
        Returns False if the circuit is OPEN and cooldown has not expired.
        """
        pid = str(plugin_id)
        now = time.time()

        try:
            redis = await get_redis()
            state = await redis.get(f"{cls._key_base(pid)}:state")
            if state == "OPEN":
                tripped_at_str = await redis.get(f"{cls._key_base(pid)}:tripped_at")
                tripped_at = float(tripped_at_str) if tripped_at_str else 0.0
                if now - tripped_at > cls.COOLDOWN_SECONDS:
                    # Half-open: allow one probe request to check if webhook has recovered
                    await redis.set(f"{cls._key_base(pid)}:state", "HALF_OPEN", ex=cls.COOLDOWN_SECONDS)
                    logger.info("plugin_circuit_breaker_half_open", plugin_id=pid)
                    return True
                return False
            return True
        except Exception as e:
            logger.warning("circuit_breaker_redis_failed_using_local", plugin_id=pid, error=str(e))
            # Fallback to in-memory state
            if pid in cls._local_tripped_at:
                tripped_at = cls._local_tripped_at[pid]
                if now - tripped_at > cls.COOLDOWN_SECONDS:
                    del cls._local_tripped_at[pid]
                    cls._local_failures[pid] = 0
                    return True
                return False
            return True

    @classmethod
    async def record_success(cls, plugin_id: UUID | str) -> None:
        """
        Record a successful webhook execution. Resets failure counter and closes circuit.
        """
        pid = str(plugin_id)
        try:
            redis = await get_redis()
            pipe = redis.pipeline()
            pipe.set(f"{cls._key_base(pid)}:state", "CLOSED")
            pipe.set(f"{cls._key_base(pid)}:failures", 0)
            pipe.delete(f"{cls._key_base(pid)}:tripped_at")
            await pipe.execute()
        except Exception as e:
            logger.warning("circuit_breaker_redis_success_failed", plugin_id=pid, error=str(e))

        cls._local_failures[pid] = 0
        cls._local_tripped_at.pop(pid, None)

    @classmethod
    async def record_failure(cls, plugin_id: UUID | str) -> bool:
        """
        Record a webhook failure or timeout.
        Returns True if the failure caused the circuit to trip OPEN.
        """
        pid = str(plugin_id)
        now = time.time()
        tripped = False

        try:
            redis = await get_redis()
            current_state = await redis.get(f"{cls._key_base(pid)}:state")
            failures = await redis.incr(f"{cls._key_base(pid)}:failures")
            await redis.expire(f"{cls._key_base(pid)}:failures", cls.COOLDOWN_SECONDS * 5)

            if current_state == "HALF_OPEN" or failures >= cls.FAILURE_THRESHOLD:
                pipe = redis.pipeline()
                pipe.set(f"{cls._key_base(pid)}:state", "OPEN", ex=cls.COOLDOWN_SECONDS * 2)
                pipe.set(f"{cls._key_base(pid)}:tripped_at", str(now), ex=cls.COOLDOWN_SECONDS * 2)
                await pipe.execute()
                tripped = True
                logger.error(
                    "plugin_circuit_breaker_tripped",
                    plugin_id=pid,
                    failures=failures,
                    state=current_state,
                )
        except Exception as e:
            logger.warning("circuit_breaker_redis_failure_failed", plugin_id=pid, error=str(e))
            local_count = cls._local_failures.get(pid, 0) + 1
            cls._local_failures[pid] = local_count
            if local_count >= cls.FAILURE_THRESHOLD:
                cls._local_tripped_at[pid] = now
                tripped = True

        return tripped

    @classmethod
    async def reset(cls, plugin_id: UUID | str) -> None:
        """Manually reset the circuit breaker for a plugin."""
        await cls.record_success(plugin_id)
