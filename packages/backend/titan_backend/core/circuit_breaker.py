import asyncio
import enum
import inspect
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import structlog

from titan_backend.core.errors import AppException

logger = structlog.get_logger("titanrag.circuit_breaker")

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    In-memory / distributed state circuit breaker.
    Trips after failure_threshold consecutive failures.
    Waits recovery_timeout_seconds before testing health in HALF_OPEN state.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()

    async def _update_state(self) -> None:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.recovery_timeout:
                logger.info("circuit_breaker_half_open_probe", name=self.name)
                self.state = CircuitState.HALF_OPEN

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            await self._update_state()
            if self.state == CircuitState.OPEN:
                raise AppException(
                    message=f"Circuit breaker for service '{self.name}' is OPEN. Operation rejected.",
                    status_code=503,
                    error_code="CIRCUIT_BREAKER_OPEN",
                )

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    logger.info("circuit_breaker_recovered", name=self.name)
                    self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result

        except Exception as e:
            # Do not count client 4xx validation errors as service failures
            if isinstance(e, AppException) and e.status_code < 500:
                raise e

            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                logger.warning(
                    "circuit_breaker_failure_recorded",
                    name=self.name,
                    count=self.failure_count,
                    threshold=self.failure_threshold,
                    error=str(e),
                )
                if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN
                    logger.error("circuit_breaker_tripped_open", name=self.name)
            raise e

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await self.call(func, *args, **kwargs)

        return wrapper


# Pre-configured circuit breakers for external dependencies
litellm_circuit_breaker = CircuitBreaker("litellm", failure_threshold=5, recovery_timeout_seconds=30.0)
qdrant_circuit_breaker = CircuitBreaker("qdrant", failure_threshold=5, recovery_timeout_seconds=30.0)
minio_circuit_breaker = CircuitBreaker("minio", failure_threshold=5, recovery_timeout_seconds=30.0)
