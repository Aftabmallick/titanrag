from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.compliance.retention import RetentionPolicyManager
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import ForbiddenError
from titan_backend.db.models.compliance import (
    RetentionAction,
    RetentionAuditLog,
    RetentionTargetResource,
)
from titan_backend.db.session import get_db

router = APIRouter(prefix="/compliance/retention", tags=["Data Retention Policies"])


class RetentionPolicyCreatePayload(BaseModel):
    workspace_id: UUID | None = None
    target_resource: RetentionTargetResource
    ttl_days: int = Field(..., ge=1, le=3650, description="Retention duration in days")
    action: RetentionAction = RetentionAction.HARD_DELETE
    is_active: bool = True


@router.get("", summary="List Data Retention Policies")
async def list_retention_policies(
    workspace_id: UUID | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    policies = await RetentionPolicyManager.list_policies(
        session=session,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
    )
    return [
        {
            "id": str(p.id),
            "workspace_id": str(p.workspace_id) if p.workspace_id else None,
            "target_resource": p.target_resource.value,
            "ttl_days": p.ttl_days,
            "action": p.action.value,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat(),
        }
        for p in policies
    ]


@router.post("", summary="Create or Update Retention Policy")
async def create_retention_policy(
    payload: RetentionPolicyCreatePayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role not in ["OWNER", "ADMIN"]:
        raise ForbiddenError("Admin privilege required to configure retention policies")

    policy = await RetentionPolicyManager.create_or_update_policy(
        session=session,
        tenant_id=current_user.tenant_id,
        workspace_id=payload.workspace_id,
        target_resource=payload.target_resource,
        ttl_days=payload.ttl_days,
        action=payload.action,
        is_active=payload.is_active,
    )
    return {
        "id": str(policy.id),
        "workspace_id": str(policy.workspace_id) if policy.workspace_id else None,
        "target_resource": policy.target_resource.value,
        "ttl_days": policy.ttl_days,
        "action": policy.action.value,
        "is_active": policy.is_active,
        "created_at": policy.created_at.isoformat(),
    }


@router.post("/{policy_id}/dry-run", summary="Calculate Dry-Run Retention Purge Impact")
async def calculate_retention_dry_run(
    policy_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await RetentionPolicyManager.calculate_dry_run_impact(session, policy_id)


@router.post("/run-now", summary="Execute Immediate Retention Sweep")
async def trigger_retention_sweep_now(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role not in ["OWNER", "ADMIN"]:
        raise ForbiddenError("Admin privilege required to trigger retention sweep")

    audit_logs = await RetentionPolicyManager.execute_all_active_sweeps(
        session=session,
        tenant_id=current_user.tenant_id,
    )
    return {
        "policies_swept": len(audit_logs),
        "total_records_purged": sum(log.records_purged for log in audit_logs),
        "total_bytes_reclaimed": sum(log.bytes_reclaimed for log in audit_logs),
        "details": [
            {
                "policy_id": str(log_entry.policy_id) if log_entry.policy_id else None,
                "resource_type": log_entry.resource_type.value,
                "records_purged": log_entry.records_purged,
                "bytes_reclaimed": log_entry.bytes_reclaimed,
                "executed_at": log_entry.executed_at.isoformat(),
            }
            for log_entry in audit_logs
        ],
    }


@router.get("/logs", summary="List Retention Execution Audit Logs")
async def list_retention_audit_logs(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(RetentionAuditLog)
        .where(RetentionAuditLog.tenant_id == current_user.tenant_id)
        .order_by(RetentionAuditLog.executed_at.desc())
        .limit(100)
    )
    logs = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(log_entry.id),
            "policy_id": str(log_entry.policy_id) if log_entry.policy_id else None,
            "resource_type": log_entry.resource_type.value,
            "records_scanned": log_entry.records_scanned,
            "records_purged": log_entry.records_purged,
            "bytes_reclaimed": log_entry.bytes_reclaimed,
            "details": log_entry.details,
            "executed_at": log_entry.executed_at.isoformat(),
        }
        for log_entry in logs
    ]
