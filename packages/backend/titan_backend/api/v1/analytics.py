from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import CurrentUser, get_current_user
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db
from titan_backend.services.analytics.engine import AnalyticsEngine
from titan_backend.services.analytics.failure_clustering import FailureClusteringService

router = APIRouter(prefix="/workspaces/{workspace_id}/analytics", tags=["Analytics & Quality"])


@router.get("/overview")
async def get_analytics_overview(
    workspace_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get query volume, user satisfaction rate, and spend overview."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return await AnalyticsEngine.get_overview_metrics(session, workspace_id, days=days)


@router.get("/failure-clusters")
async def get_failure_clusters(
    workspace_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get semantic failure clusters of negative feedback and citation issues."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    clusters = await FailureClusteringService.cluster_failed_queries(session, workspace_id, limit=limit)
    return {"clusters": clusters}


@router.get("/latency-breakdown")
async def get_latency_breakdown(
    workspace_id: UUID,
    days: int = Query(7, ge=1, le=90),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get P50, P90, P95, and P99 latency stats and stage-by-stage waterfall breakdown."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return await AnalyticsEngine.get_latency_breakdown(session, workspace_id, days=days)
