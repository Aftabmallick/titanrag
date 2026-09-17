from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from titan_backend.clients.redis_client import get_redis

logger = structlog.get_logger(__name__)


class QuotaExceededException(HTTPException):
    def __init__(self, current_cu: float, max_cu: float, requested_cu: float):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "QUOTA_EXCEEDED",
                "message": f"Monthly Compute Unit limit exceeded: current {current_cu:.2f} CU + requested {requested_cu:.2f} CU > limit {max_cu:.2f} CU.",
                "current_compute_units": current_cu,
                "limit_compute_units": max_cu,
                "requested_compute_units": requested_cu,
            },
        )


class FinOpsGatekeeper:
    @staticmethod
    def _month_key(tenant_id: UUID) -> str:
        current_month = datetime.now(UTC).strftime("%Y-%m")
        return f"quota:cu:{tenant_id}:{current_month}"

    @classmethod
    async def get_current_usage(cls, tenant_id: UUID) -> float:
        try:
            redis = await get_redis()
            key = cls._month_key(tenant_id)
            val = await redis.get(key)
            return float(val) if val is not None else 0.0
        except Exception as e:
            logger.warning("failed_reading_redis_quota", tenant_id=str(tenant_id), error=str(e))
            return 0.0

    @classmethod
    async def check_and_reserve_quota(
        cls,
        tenant_id: UUID,
        estimated_cu: float,
        max_monthly_cu: float | None = None,
    ) -> float:
        """Atomically checks if estimated_cu fits in remaining quota.

        If max_monthly_cu is None or 0, quota is unlimited.
        Raises QuotaExceededException if exceeded.
        Returns the current CU usage before reservation.
        """
        if max_monthly_cu is None or max_monthly_cu <= 0:
            return await cls.get_current_usage(tenant_id)

        current_usage = await cls.get_current_usage(tenant_id)
        if current_usage + estimated_cu > max_monthly_cu:
            logger.warning(
                "quota_limit_hit",
                tenant_id=str(tenant_id),
                current=current_usage,
                requested=estimated_cu,
                max=max_monthly_cu,
            )
            raise QuotaExceededException(
                current_cu=current_usage,
                max_cu=max_monthly_cu,
                requested_cu=estimated_cu,
            )

        return current_usage

    @classmethod
    async def record_usage(
        cls,
        tenant_id: UUID,
        cu_consumed: float,
        max_monthly_cu: float | None = None,
    ) -> dict[str, float]:
        """Increments sliding window counter in Redis and checks alert thresholds."""
        try:
            redis = await get_redis()
            key = cls._month_key(tenant_id)
            new_val = await redis.incrbyfloat(key, cu_consumed)
            # Set TTL to 35 days (3,024,000s)
            await redis.expire(key, 3024000)

            result = {"current_usage": float(new_val), "limit": max_monthly_cu or 0.0}

            # Check threshold alerts (80%, 90%)
            if max_monthly_cu and max_monthly_cu > 0:
                percent = (float(new_val) / max_monthly_cu) * 100
                result["percent_used"] = percent
                if percent >= 90:
                    logger.warning("finops_quota_critical", tenant_id=str(tenant_id), percent=percent)
                elif percent >= 80:
                    logger.info("finops_quota_warning", tenant_id=str(tenant_id), percent=percent)

            return result
        except Exception as e:
            logger.error("failed_recording_finops_usage", tenant_id=str(tenant_id), error=str(e))
            return {"current_usage": 0.0, "limit": 0.0}
