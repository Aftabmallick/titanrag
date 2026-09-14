import datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException
from titan_backend.db.models.documents import Document, DocumentStatus

logger = structlog.get_logger("titanrag.quotas")

# Weighted CU Cost Table
CU_COSTS = {
    "text_query": 1,
    "ocr_page": 3,
    "batched_context_window": 5,
    "colpali_page": 10,
}


async def consume_compute_units(
    tenant_id: UUID,
    operation: str,
    units: int = 1,
    max_monthly_quota: int | None = None,
) -> int:
    """
    Records CU consumption and verifies monthly budget.
    Raises 429 Quota Exceeded if tenant has exhausted monthly compute units.
    Returns: new monthly total CU
    """
    cost_per_unit = CU_COSTS.get(operation, 1)
    total_cu = cost_per_unit * units
    quota = max_monthly_quota or settings.DEFAULT_MONTHLY_CU_QUOTA

    month_key = datetime.datetime.now(datetime.UTC).strftime("%Y-%m")
    redis_key = f"tenant_cu:{tenant_id}:{month_key}"

    try:
        redis = await get_redis_client()
        current_cu = await redis.incrby(redis_key, total_cu)
        if current_cu == total_cu:
            # Set 35-day expiry on first monthly key write
            await redis.expire(redis_key, 35 * 86400)

        if current_cu > quota:
            logger.warning(
                "tenant_cu_quota_exceeded",
                tenant_id=str(tenant_id),
                current_cu=current_cu,
                quota=quota,
                operation=operation,
            )
            raise AppException(
                message=f"Monthly Compute Unit (CU) quota exceeded ({current_cu}/{quota} CU). Please upgrade your tier.",
                status_code=429,
                error_code="QUOTA_EXCEEDED",
                details={"current_cu": current_cu, "monthly_quota": quota, "operation": operation},
            )

        return int(current_cu)
    except AppException:
        raise
    except Exception as e:
        logger.warning("compute_unit_tracking_error", tenant_id=str(tenant_id), error=str(e))
        return 0


async def check_storage_quota(
    tenant_id: UUID,
    additional_bytes: int,
    max_storage_bytes: int = 10 * 1024 * 1024 * 1024,  # 10GB default
) -> int:
    """
    Checks if adding additional_bytes exceeds the tenant's max storage bytes quota.
    """
    redis_key = f"tenant_storage_bytes:{tenant_id}"
    try:
        redis = await get_redis_client()
        current_bytes = await redis.incrby(redis_key, additional_bytes)
        if current_bytes > max_storage_bytes:
            await redis.decrby(redis_key, additional_bytes)
            raise AppException(
                message=f"Storage quota exceeded ({current_bytes}/{max_storage_bytes} bytes).",
                status_code=429,
                error_code="STORAGE_QUOTA_EXCEEDED",
                details={"current_bytes": current_bytes, "max_storage_bytes": max_storage_bytes},
            )
        return int(current_bytes)
    except AppException:
        raise
    except Exception as e:
        logger.warning("storage_quota_tracking_error", tenant_id=str(tenant_id), error=str(e))
        return 0


async def check_document_quota(
    tenant_id: UUID,
    db: AsyncSession,
    max_documents: int = 10000,
) -> int:
    """
    Checks if active document count exceeds the tenant's max document quota.
    """
    stmt = select(func.count(Document.id)).where(
        Document.tenant_id == tenant_id,
        Document.status != DocumentStatus.FAILED,
    )
    res = await db.execute(stmt)
    doc_count = res.scalar_one_or_none() or 0
    if doc_count >= max_documents:
        raise AppException(
            message=f"Document count quota exceeded ({doc_count}/{max_documents} documents).",
            status_code=429,
            error_code="DOCUMENT_QUOTA_EXCEEDED",
            details={"current_documents": doc_count, "max_documents": max_documents},
        )
    return int(doc_count)


async def check_daily_query_quota(
    tenant_id: UUID,
    max_queries_per_day: int = 5000,
) -> int:
    """
    Sliding/daily query counter to prevent noisy neighbor denial of service.
    """
    day_key = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    redis_key = f"tenant_queries:{tenant_id}:{day_key}"
    try:
        redis = await get_redis_client()
        queries = await redis.incr(redis_key)
        if queries == 1:
            await redis.expire(redis_key, 2 * 86400)
        if queries > max_queries_per_day:
            raise AppException(
                message=f"Daily query quota exceeded ({queries}/{max_queries_per_day} queries).",
                status_code=429,
                error_code="QUERY_QUOTA_EXCEEDED",
                details={"current_queries": queries, "daily_quota": max_queries_per_day},
            )
        return int(queries)
    except AppException:
        raise
    except Exception as e:
        logger.warning("daily_query_tracking_error", tenant_id=str(tenant_id), error=str(e))
        return 0
