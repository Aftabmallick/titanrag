from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import CurrentUser, get_current_user
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db
from titan_backend.services.finops.gatekeeper import FinOpsGatekeeper
from titan_backend.services.finops.ledger import FinOpsLedgerService

router = APIRouter(prefix="/workspaces/{workspace_id}/finops", tags=["FinOps"])


class BudgetUpdateRequest(BaseModel):
    max_compute_units: float = Field(..., ge=0, description="Monthly CU limit (0 for unlimited)")


@router.get("/usage")
async def get_finops_usage(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve real-time monthly Compute Unit consumption vs configured quota."""
    # Verify workspace membership
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    current_cu = await FinOpsGatekeeper.get_current_usage(current_user.tenant_id)
    ws_settings = getattr(workspace, "settings", {}) or {}
    quota = ws_settings.get("quota_limits", {}) if isinstance(ws_settings, dict) else {}
    max_cu = float(quota.get("max_compute_units", 0.0))

    percent = (current_cu / max_cu * 100) if max_cu > 0 else 0.0

    return {
        "workspace_id": str(workspace_id),
        "tenant_id": str(current_user.tenant_id),
        "current_month_compute_units": current_cu,
        "max_monthly_compute_units": max_cu,
        "percent_utilized": round(percent, 2),
        "status": "CRITICAL" if percent >= 90 else "WARNING" if percent >= 80 else "HEALTHY",
    }


@router.get("/breakdown")
async def get_finops_breakdown(
    workspace_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get categorized Ingestion vs. Retrieval cost and CU attribution over time."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return await FinOpsLedgerService.get_workspace_breakdown(session, workspace_id, days=days)


@router.put("/budget")
async def update_workspace_budget(
    workspace_id: UUID,
    request: BudgetUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update workspace monthly Compute Unit budget cap."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    ws_settings = dict(getattr(workspace, "settings", {}) or {})
    quota = dict(ws_settings.get("quota_limits", {}))
    quota["max_compute_units"] = request.max_compute_units
    ws_settings["quota_limits"] = quota
    workspace.settings = ws_settings

    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)

    return {
        "workspace_id": str(workspace_id),
        "max_compute_units": request.max_compute_units,
        "message": "Budget cap updated successfully",
    }
