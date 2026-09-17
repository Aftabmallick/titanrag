from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from titan_backend.clients.redis_client import get_redis

logger = structlog.get_logger(__name__)

# TTL for monthly quota keys: 35 days in seconds (covers full month + buffer)
_QUOTA_TTL_SECONDS = 3_024_000

# Lua script: atomically check + increment CU quota in a single Redis roundtrip.
# Eliminates TOCTOU race where two concurrent requests could both pass the budget
# check before either one increments the counter.
#
# KEYS[1] = quota key
# ARGV[1] = requested CU (float as string)
# ARGV[2] = max allowed CU (float as string)
# ARGV[3] = TTL in seconds
#
# Returns: {allowed (0|1), current_value_after (float as string)}
_QUOTA_CHECK_AND_RESERVE_LUA = """
local key = KEYS[1]
local requested = tonumber(ARGV[1])
local max_cu = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local current = tonumber(redis.call('GET', key) or '0')
if current == nil then
    current = 0.0
end

if (current + requested) > max_cu then
    -- Over budget: reject without incrementing
    return {0, tostring(current)}
end

-- Within budget: atomically increment and set TTL
local new_val = redis.call('INCRBYFLOAT', key, ARGV[1])
redis.call('EXPIRE', key, ttl)
return {1, tostring(new_val)}
"""


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
        """Reads the current month's CU consumption from Redis (non-blocking read)."""
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
        """Atomically checks if estimated_cu fits within the remaining monthly quota
        and reserves it in a single Redis roundtrip using a Lua script.

        If max_monthly_cu is None or <= 0, quota is unlimited (no reservation needed).
        Raises QuotaExceededException if the reservation would exceed the limit.
        Returns the new CU usage after successful reservation.
        """
        if max_monthly_cu is None or max_monthly_cu <= 0:
            return await cls.get_current_usage(tenant_id)

        try:
            redis = await get_redis()
            key = cls._month_key(tenant_id)

            # Execute atomic Lua script: check + reserve in one roundtrip
            result = await redis.eval(
                _QUOTA_CHECK_AND_RESERVE_LUA,
                1,  # number of KEYS
                key,
                str(estimated_cu),
                str(max_monthly_cu),
                str(_QUOTA_TTL_SECONDS),
            )

            allowed = int(result[0])
            current_value = float(result[1])

            if not allowed:
                logger.warning(
                    "quota_limit_hit_atomic",
                    tenant_id=str(tenant_id),
                    current=current_value,
                    requested=estimated_cu,
                    max=max_monthly_cu,
                )
                raise QuotaExceededException(
                    current_cu=current_value,
                    max_cu=max_monthly_cu,
                    requested_cu=estimated_cu,
                )

            # Check threshold alerts on successful reservation
            percent = (current_value / max_monthly_cu) * 100
            if percent >= 90:
                logger.warning(
                    "finops_quota_critical",
                    tenant_id=str(tenant_id),
                    percent=round(percent, 1),
                    current_cu=current_value,
                    max_cu=max_monthly_cu,
                )
            elif percent >= 80:
                logger.info(
                    "finops_quota_warning",
                    tenant_id=str(tenant_id),
                    percent=round(percent, 1),
                    current_cu=current_value,
                    max_cu=max_monthly_cu,
                )

            return current_value

        except QuotaExceededException:
            raise
        except Exception as e:
            # On Redis failure, log and allow (fail-open for availability)
            logger.error(
                "quota_check_redis_error_fail_open",
                tenant_id=str(tenant_id),
                error=str(e),
            )
            return 0.0

    @classmethod
    async def record_usage(
        cls,
        tenant_id: UUID,
        cu_consumed: float,
        max_monthly_cu: float | None = None,
        session: Any | None = None,
        workspace_id: UUID | None = None,
        operation_type: Any | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        user_id: UUID | None = None,
        request_id: str | None = None,
        model_name: str | None = None,
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """Increments the sliding-window counter in Redis and checks alert thresholds.

        If a database session and workspace_id are provided, dual-writes the record
        to the persistent PostgreSQL FinOps ledger.
        """
        try:
            redis = await get_redis()
            key = cls._month_key(tenant_id)
            new_val = await redis.incrbyfloat(key, cu_consumed)
            await redis.expire(key, _QUOTA_TTL_SECONDS)

            result: dict[str, float] = {"current_usage": float(new_val), "limit": max_monthly_cu or 0.0}

            # Check threshold alerts (80%, 90%)
            if max_monthly_cu and max_monthly_cu > 0:
                percent = (float(new_val) / max_monthly_cu) * 100
                result["percent_used"] = percent
                if percent >= 90:
                    logger.warning("finops_quota_critical", tenant_id=str(tenant_id), percent=percent)
                elif percent >= 80:
                    logger.info("finops_quota_warning", tenant_id=str(tenant_id), percent=percent)

            # Optional dual-write to PostgreSQL FinOps Ledger
            if session is not None and workspace_id is not None and operation_type is not None:
                try:
                    from titan_backend.services.finops.ledger import FinOpsLedgerService

                    await FinOpsLedgerService.record_transaction(
                        session=session,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        operation_type=operation_type,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        user_id=user_id,
                        request_id=request_id,
                        model_name=model_name,
                        provider=provider,
                        details=details,
                    )
                except Exception as db_err:
                    logger.error("finops_ledger_dual_write_failed", error=str(db_err), tenant_id=str(tenant_id))

            return result
        except Exception as e:
            logger.error("failed_recording_finops_usage", tenant_id=str(tenant_id), error=str(e))
            return {"current_usage": 0.0, "limit": 0.0}
