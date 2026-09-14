import asyncio

import structlog
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from titan_backend.clients.qdrant_client import check_qdrant_health
from titan_backend.clients.redis_client import check_redis_health
from titan_backend.clients.s3_client import check_minio_health
from titan_backend.core.config import settings
from titan_backend.db.session import async_session_factory

logger = structlog.get_logger("titanrag.health")

router = APIRouter(tags=["Health"])


class DependencyStatus(BaseModel):
    status: str
    latency_ms: float
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    dependencies: dict[str, DependencyStatus]


@router.get("/health/live", summary="Liveness Probe", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", summary="Readiness Probe", response_model=HealthResponse)
async def readiness(response: Response) -> HealthResponse:
    tasks = {
        "postgres": check_postgres_health(),
        "qdrant": check_qdrant_health(),
    }
    results: dict[str, DependencyStatus] = {}

    if settings.QUICKSTART_MODE:
        results["redis"] = DependencyStatus(status="skipped", latency_ms=0.0, error="Quickstart profile active")
        results["minio"] = DependencyStatus(status="skipped", latency_ms=0.0, error="Quickstart profile active")
    else:
        tasks["redis"] = check_redis_health()
        tasks["minio"] = check_minio_health()

    all_healthy = True

    for name, coro in tasks.items():
        start = asyncio.get_event_loop().time()
        try:
            is_ok = await asyncio.wait_for(coro, timeout=3.0)
            latency = round((asyncio.get_event_loop().time() - start) * 1000, 2)
            if is_ok:
                results[name] = DependencyStatus(status="ok", latency_ms=latency)
            else:
                results[name] = DependencyStatus(status="down", latency_ms=latency, error="Probe returned false")
                all_healthy = False
        except Exception as e:
            latency = round((asyncio.get_event_loop().time() - start) * 1000, 2)
            results[name] = DependencyStatus(status="down", latency_ms=latency, error=str(e))
            all_healthy = False

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", dependencies=results)

    return HealthResponse(status="ready", dependencies=results)


async def check_postgres_health() -> bool:
    try:
        async with async_session_factory() as session:
            res = await session.execute(text("SELECT 1"))
            return res.scalar() == 1
    except Exception as e:
        logger.warning("postgres_health_check_failed", error=str(e))
        return False
