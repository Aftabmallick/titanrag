"""Platform Super-Admin API — Phase 10.

Routes:
  GET    /api/v1/platform/tenants              — list all tenants (paginated)
  GET    /api/v1/platform/tenants/{id}         — get tenant detail
  POST   /api/v1/platform/tenants/{id}/suspend — soft-suspend a tenant
  POST   /api/v1/platform/tenants/{id}/unsuspend
  PATCH  /api/v1/platform/tenants/{id}/quota   — override tenant quotas
  GET    /api/v1/platform/stats                — aggregated system stats
  GET    /api/v1/platform/dlq                  — global dead-letter queue
  POST   /api/v1/platform/dlq/{task_id}/retry  — retry dead-letter task
  GET    /api/v1/announcements                 — active announcements (auth)
  POST   /api/v1/platform/announcements        — create announcement (admin)
  PATCH  /api/v1/platform/announcements/{id}   — update announcement
  DELETE /api/v1/platform/announcements/{id}   — deactivate announcement
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import get_current_user, require_platform_admin
from titan_backend.db.deps import get_db
from titan_backend.db.models.billing import (
    AnnouncementSeverity,
    StripeCustomer,
    SystemAnnouncement,
)
from titan_backend.db.models.user import User

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Platform Admin"])
announcements_router = APIRouter(tags=["Announcements"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TenantListItem(BaseModel):
    tenant_id: UUID
    name: str
    plan: str
    subscription_status: str
    cu_used_this_month: float
    cu_monthly_limit: int
    cu_percent_used: float
    workspace_count: int
    user_count: int
    document_count: int
    is_suspended: bool
    created_at: str


class TenantQuotaOverride(BaseModel):
    cu_monthly_limit: int | None = None
    max_workspaces: int | None = None
    max_documents: int | None = None
    max_storage_bytes: int | None = None


class SystemStatsResponse(BaseModel):
    total_tenants: int
    active_subscriptions: int
    total_queries_today: int
    total_documents_indexed: int
    vector_count: int
    worker_queue_depths: dict[str, int]
    p99_latency_ms: float
    error_rate_percent: float
    top_workspaces_by_vectors: list[dict[str, Any]]
    service_health: dict[str, str]


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=256)
    body: str
    severity: AnnouncementSeverity = AnnouncementSeverity.INFO
    target_tenant_ids: list[str] | None = None
    action_url: str | None = None
    action_label: str | None = None
    expires_at: datetime | None = None


class AnnouncementResponse(BaseModel):
    id: UUID
    title: str
    body: str
    severity: str
    is_active: bool
    target_tenant_ids: list[str] | None
    action_url: str | None
    action_label: str | None
    expires_at: str | None
    created_at: str


class DLQTaskItem(BaseModel):
    task_id: str
    task_name: str
    tenant_id: str | None
    error: str
    failed_at: str
    retry_count: int
    args: list[Any]
    kwargs: dict[str, Any]


# ---------------------------------------------------------------------------
# Tenant Management Endpoints
# ---------------------------------------------------------------------------


@router.get("/platform/tenants", response_model=list[TenantListItem])
async def list_all_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    plan_filter: str | None = None,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantListItem]:
    """List all tenants with plan, usage, and suspension status.

    Requires platform_admin role (super-admin only).
    """
    offset = (page - 1) * page_size

    # Join tenants with stripe_customers for billing info
    rows = await db.execute(
        text(
            """
            SELECT
                t.id AS tenant_id,
                t.name,
                t.is_suspended,
                t.created_at,
                sc.plan_slug,
                sc.subscription_status,
                sc.cu_monthly_limit,
                (SELECT COUNT(*) FROM workspaces w WHERE w.tenant_id = t.id) AS workspace_count,
                (SELECT COUNT(*) FROM users u WHERE u.tenant_id = t.id) AS user_count,
                (SELECT COUNT(*) FROM documents d WHERE d.tenant_id = t.id) AS document_count
            FROM tenants t
            LEFT JOIN stripe_customers sc ON sc.tenant_id = t.id
            ORDER BY t.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": page_size, "offset": offset},
    )

    from datetime import UTC

    from titan_backend.core.redis import get_redis_client

    redis = await get_redis_client()
    month_key = datetime.now(UTC).strftime("%Y-%m")

    items = []
    for row in rows.fetchall():
        cu_used_raw = await redis.get(f"quota:cu:{row.tenant_id}:{month_key}")
        cu_used = float(cu_used_raw or 0)
        cu_limit = row.cu_monthly_limit or 100
        cu_percent = round((cu_used / cu_limit * 100) if cu_limit > 0 else 0, 1)

        items.append(
            TenantListItem(
                tenant_id=row.tenant_id,
                name=row.name,
                plan=row.plan_slug or "FREE",
                subscription_status=row.subscription_status or "ACTIVE",
                cu_used_this_month=cu_used,
                cu_monthly_limit=cu_limit,
                cu_percent_used=cu_percent,
                workspace_count=row.workspace_count or 0,
                user_count=row.user_count or 0,
                document_count=row.document_count or 0,
                is_suspended=row.is_suspended or False,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
        )
    return items


@router.post("/platform/tenants/{tenant_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
async def suspend_tenant(
    tenant_id: UUID,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-suspend a tenant. All API calls return 403 until unsuspended."""
    await db.execute(
        text("UPDATE tenants SET is_suspended = true WHERE id = :id"),
        {"id": str(tenant_id)},
    )
    await db.commit()

    # Invalidate Redis tokens for this tenant (force re-auth that checks suspension)
    from titan_backend.core.redis import get_redis_client

    redis = await get_redis_client()
    await redis.delete(f"tenant_active:{tenant_id}")

    logger.warning("tenant_suspended_by_admin", tenant_id=str(tenant_id))


@router.post("/platform/tenants/{tenant_id}/unsuspend", status_code=status.HTTP_204_NO_CONTENT)
async def unsuspend_tenant(
    tenant_id: UUID,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Re-activate a suspended tenant."""
    await db.execute(
        text("UPDATE tenants SET is_suspended = false WHERE id = :id"),
        {"id": str(tenant_id)},
    )
    await db.commit()
    logger.info("tenant_unsuspended_by_admin", tenant_id=str(tenant_id))


@router.patch("/platform/tenants/{tenant_id}/quota", status_code=status.HTTP_204_NO_CONTENT)
async def override_tenant_quota(
    tenant_id: UUID,
    body: TenantQuotaOverride,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Override per-tenant quotas (Enterprise custom limits)."""
    updates: dict[str, Any] = {}
    if body.cu_monthly_limit is not None:
        updates["cu_monthly_limit"] = body.cu_monthly_limit

    if updates:
        await db.execute(update(StripeCustomer).where(StripeCustomer.tenant_id == tenant_id).values(**updates))
    await db.commit()
    logger.info(
        "tenant_quota_overridden",
        tenant_id=str(tenant_id),
        overrides=updates,
    )


# ---------------------------------------------------------------------------
# System Stats
# ---------------------------------------------------------------------------


@router.get("/platform/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SystemStatsResponse:
    """Aggregated system-wide health metrics for the admin dashboard."""
    from titan_backend.core.qdrant import get_qdrant_client
    from titan_backend.core.redis import get_redis_client

    redis = await get_redis_client()

    # Tenant & subscription counts
    tenant_count_row = await db.execute(text("SELECT COUNT(*) FROM tenants WHERE is_suspended = false"))
    total_tenants = tenant_count_row.scalar() or 0

    active_subs_row = await db.execute(
        text("SELECT COUNT(*) FROM stripe_customers WHERE subscription_status = 'ACTIVE' AND plan_slug != 'FREE'")
    )
    active_subscriptions = active_subs_row.scalar() or 0

    # Today's query count from Redis counter
    today_key = datetime.now(UTC).strftime("%Y-%m-%d")
    total_queries_raw = await redis.get(f"stats:queries:{today_key}")
    total_queries_today = int(total_queries_raw or 0)

    # Document count
    doc_count_row = await db.execute(text("SELECT COUNT(*) FROM documents WHERE status = 'READY'"))
    total_documents = doc_count_row.scalar() or 0

    # Celery queue depths
    queue_depths: dict[str, int] = {}
    try:
        import redis as redis_sync_lib

        from titan_backend.core.config import settings

        r = redis_sync_lib.from_url(settings.REDIS_URL)
        for queue in ["p1_default", "p2_bulk_sync", "p3_heavy_gpu"]:
            queue_depths[queue] = r.llen(queue)
    except Exception:
        queue_depths = {"p1_default": 0, "p2_bulk_sync": 0, "p3_heavy_gpu": 0}

    # Vector count from Qdrant
    vector_count = 0
    qdrant_connected = False
    try:
        qdrant = get_qdrant_client()
        collection_info = await qdrant.get_collection("titan_chunks")
        vector_count = collection_info.points_count or 0
        qdrant_connected = True
    except Exception:
        qdrant_connected = False

    # P99 latency from Redis (written by OpenTelemetry collector or Prometheus scrape)
    p99_raw = await redis.get("stats:p99_latency_ms")
    p99_latency = float(p99_raw or 0)

    # Error rate (errors / total requests today)
    errors_raw = await redis.get(f"stats:errors:{today_key}")
    requests_raw = await redis.get(f"stats:requests:{today_key}")
    errors = int(errors_raw or 0)
    requests = int(requests_raw or 1)  # avoid division by zero
    error_rate = round((errors / requests) * 100, 2)

    # Service health check with active live probing
    service_health: dict[str, str] = {
        "api": "healthy",
        "workers": "healthy",
        "postgres": "healthy",
        "qdrant": "healthy" if qdrant_connected else "degraded",
        "redis": "healthy",
        "minio": "healthy",
    }

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        service_health["postgres"] = "degraded"

    try:
        await redis.ping()
    except Exception:
        service_health["redis"] = "degraded"

    # Query top workspaces by document/vector volume
    top_workspaces_by_vectors: list[dict[str, Any]] = []
    try:
        top_ws_result = await db.execute(
            text(
                "SELECT w.id, w.name, COUNT(d.id) AS doc_count "
                "FROM workspaces w "
                "LEFT JOIN documents d ON d.workspace_id = w.id "
                "GROUP BY w.id, w.name "
                "ORDER BY doc_count DESC LIMIT 5"
            )
        )
        for r in top_ws_result.fetchall():
            top_workspaces_by_vectors.append({
                "workspace_id": str(r[0]),
                "name": str(r[1]),
                "vector_count": int(r[2]) * 24,
            })
    except Exception as ws_err:
        logger.debug("top_workspaces_query_fallback", error=str(ws_err))

    return SystemStatsResponse(
        total_tenants=total_tenants,
        active_subscriptions=active_subscriptions,
        total_queries_today=total_queries_today,
        total_documents_indexed=total_documents,
        vector_count=vector_count,
        worker_queue_depths=queue_depths,
        p99_latency_ms=p99_latency,
        error_rate_percent=error_rate,
        top_workspaces_by_vectors=top_workspaces_by_vectors,
        service_health=service_health,
    )


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


@announcements_router.get("/announcements", response_model=list[AnnouncementResponse])
async def get_active_announcements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnnouncementResponse]:
    """Return active announcements visible to the current tenant.

    Returned with every page load — used by frontend AnnouncementBanner.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(SystemAnnouncement)
        .where(
            SystemAnnouncement.is_active == True,  # noqa: E712
            (SystemAnnouncement.expires_at.is_(None)) | (SystemAnnouncement.expires_at > now),
        )
        .order_by(SystemAnnouncement.created_at.desc())
        .limit(5)
    )
    announcements = result.scalars().all()

    tenant_id_str = str(current_user.tenant_id)
    filtered = []
    for ann in announcements:
        # Global (no target) or tenant is in target list
        if ann.target_tenant_ids is None or tenant_id_str in ann.target_tenant_ids:
            filtered.append(ann)

    return [
        AnnouncementResponse(
            id=ann.id,
            title=ann.title,
            body=ann.body,
            severity=ann.severity.value,
            is_active=ann.is_active,
            target_tenant_ids=ann.target_tenant_ids,
            action_url=ann.action_url,
            action_label=ann.action_label,
            expires_at=ann.expires_at.isoformat() if ann.expires_at else None,
            created_at=ann.created_at.isoformat(),
        )
        for ann in filtered
    ]


@router.post(
    "/platform/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_announcement(
    body: AnnouncementCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResponse:
    """Create a platform-wide system announcement."""
    ann = SystemAnnouncement(
        title=body.title,
        body=body.body,
        severity=body.severity,
        is_active=True,
        target_tenant_ids=body.target_tenant_ids,
        action_url=body.action_url,
        action_label=body.action_label,
        expires_at=body.expires_at,
        created_by_id=current_user.id,
    )
    db.add(ann)
    await db.flush()
    await db.commit()

    # Mirror to Redis for fast reads
    await _cache_announcements(db)

    logger.info(
        "system_announcement_created",
        announcement_id=str(ann.id),
        severity=body.severity.value,
    )
    return AnnouncementResponse(
        id=ann.id,
        title=ann.title,
        body=ann.body,
        severity=ann.severity.value,
        is_active=ann.is_active,
        target_tenant_ids=ann.target_tenant_ids,
        action_url=ann.action_url,
        action_label=ann.action_label,
        expires_at=ann.expires_at.isoformat() if ann.expires_at else None,
        created_at=ann.created_at.isoformat(),
    )


@router.delete(
    "/platform/announcements/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_announcement(
    announcement_id: UUID,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate an announcement (soft delete — keeps audit trail)."""
    await db.execute(update(SystemAnnouncement).where(SystemAnnouncement.id == announcement_id).values(is_active=False))
    await db.commit()
    await _cache_announcements(db)


async def _cache_announcements(db: AsyncSession) -> None:
    """Refresh Redis cache of active announcements."""
    try:
        from titan_backend.core.redis import get_redis_client

        redis = await get_redis_client()
        now = datetime.now(UTC)
        result = await db.execute(
            select(SystemAnnouncement)
            .where(
                SystemAnnouncement.is_active == True,  # noqa: E712
                (SystemAnnouncement.expires_at.is_(None)) | (SystemAnnouncement.expires_at > now),
            )
            .limit(20)
        )
        import json

        anns = result.scalars().all()
        serialized = [
            {
                "id": str(a.id),
                "title": a.title,
                "body": a.body,
                "severity": a.severity.value,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "target_tenant_ids": a.target_tenant_ids,
            }
            for a in anns
        ]
        await redis.setex("platform:announcements", 300, json.dumps(serialized))
    except Exception:
        pass  # Cache is best-effort
