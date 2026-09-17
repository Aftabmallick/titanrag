from fastapi import HTTPException, status
import structlog
from titan_backend.clients.redis_client import get_redis_client

logger = structlog.get_logger("titanrag.backpressure")

DEFAULT_MAX_QUEUE_DEPTH = 500  # Max pending Celery tasks across queues before backpressure trips
MONITORED_QUEUES = ["p0_interactive", "p1_default", "p2_bulk_sync", "heavy_ml"]


class ServiceDegradedException(HTTPException):
    def __init__(self, queue_depth: int, max_allowed: int, retry_after: int = 30):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "SERVICE_DEGRADED",
                "message": (
                    f"System is currently experiencing high load (Queue Depth: {queue_depth} tasks, "
                    f"limit: {max_allowed}). Ingestion temporarily throttled."
                ),
                "queue_depth": queue_depth,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


class BackpressureController:
    """Monitors worker queue saturation and sheds incoming ingestion load

    with HTTP 503 Service Unavailable + Retry-After headers to prevent out-of-memory crashes.
    """

    def __init__(self, max_depth: int = DEFAULT_MAX_QUEUE_DEPTH):
        self.max_depth = max_depth

    async def get_total_queue_depth(self) -> int:
        try:
            redis = await get_redis_client()
            total = 0
            for q in MONITORED_QUEUES:
                depth = await redis.llen(q)
                total += depth
            return total
        except Exception as e:
            logger.warning("backpressure_queue_depth_check_failed", error=str(e))
            return 0

    async def check_ingestion_backpressure(self) -> None:
        """Raises ServiceDegradedException if background worker queue depth exceeds threshold."""
        depth = await self.get_total_queue_depth()
        if depth >= self.max_depth:
            logger.warning("backpressure_tripped_503_shed", queue_depth=depth, max_allowed=self.max_depth)
            raise ServiceDegradedException(queue_depth=depth, max_allowed=self.max_depth, retry_after=30)


backpressure_controller = BackpressureController()


async def verify_ingestion_backpressure() -> None:
    """FastAPI dependency for ingestion endpoints."""
    await backpressure_controller.check_ingestion_backpressure()
