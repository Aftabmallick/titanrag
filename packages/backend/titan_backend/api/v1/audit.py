from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import AppException
from titan_backend.db.models.audit import AuditLog
from titan_backend.db.session import get_db

router = APIRouter(prefix="/admin/audit-log", tags=["Audit Log"])


class AuditLogEntryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, Any]
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[AuditLogEntryResponse])
async def query_audit_logs(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    user_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogEntryResponse]:
    if current_user.role not in {"ADMIN", "OWNER"} and not current_user.is_superuser:
        raise AppException(message="Only organization admins can inspect audit logs", status_code=403)

    stmt = select(AuditLog).where(AuditLog.tenant_id == current_user.tenant_id)

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    entries = res.scalars().all()

    return [AuditLogEntryResponse.model_validate(e) for e in entries]
