from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import CurrentUser, get_current_user, get_db
from titan_backend.connectors.cdc_manager import CdcDeltaSyncManager
from titan_backend.connectors.factory import get_connector
from titan_backend.db.models.connectors import Connector, ConnectorStatus, ConnectorSyncLog

router = APIRouter(prefix="/workspaces/{workspace_id}/connectors", tags=["connectors"])


class ConnectorCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    connector_type: str = Field(..., description="gdrive, sharepoint, confluence, notion")
    config: dict[str, Any] = Field(default_factory=dict)
    auth_credentials: dict[str, Any] = Field(default_factory=dict)
    sync_schedule: str | None = Field(None, description="Optional cron schedule")


class ConnectorResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    connector_type: str
    status: str
    config: dict[str, Any]
    sync_schedule: str | None
    last_synced_at: str | None
    sync_stats: dict[str, Any]
    last_sync_error: str | None
    created_at: str


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    workspace_id: uuid.UUID,
    payload: ConnectorCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new SaaS connector for the workspace."""
    # Validate connector type
    try:
        instance = get_connector(payload.connector_type, payload.config, payload.auth_credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    connector = Connector(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        name=payload.name,
        connector_type=payload.connector_type.lower().strip(),
        status=ConnectorStatus.ACTIVE,
        config=payload.config,
        auth_credentials=payload.auth_credentials,
        sync_schedule=payload.sync_schedule,
        cdc_cursor={},
        sync_stats={},
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)

    return ConnectorResponse(
        id=str(connector.id),
        tenant_id=str(connector.tenant_id),
        workspace_id=str(connector.workspace_id),
        name=connector.name,
        connector_type=connector.connector_type,
        status=connector.status.value,
        config=connector.config,
        sync_schedule=connector.sync_schedule,
        last_synced_at=connector.last_synced_at.isoformat() if connector.last_synced_at else None,
        sync_stats=connector.sync_stats,
        last_sync_error=connector.last_sync_error,
        created_at=connector.created_at.isoformat(),
    )


@router.get("", response_model=list[ConnectorResponse])
async def list_connectors(
    workspace_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connectors registered in the workspace."""
    stmt = select(Connector).where(
        Connector.workspace_id == workspace_id,
        Connector.tenant_id == current_user.tenant_id,
    ).order_by(desc(Connector.created_at))
    result = await db.execute(stmt)
    connectors = result.scalars().all()

    return [
        ConnectorResponse(
            id=str(c.id),
            tenant_id=str(c.tenant_id),
            workspace_id=str(c.workspace_id),
            name=c.name,
            connector_type=c.connector_type,
            status=c.status.value,
            config=c.config,
            sync_schedule=c.sync_schedule,
            last_synced_at=c.last_synced_at.isoformat() if c.last_synced_at else None,
            sync_stats=c.sync_stats,
            last_sync_error=c.last_sync_error,
            created_at=c.created_at.isoformat(),
        )
        for c in connectors
    ]


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector_details(
    workspace_id: uuid.UUID,
    connector_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.workspace_id == workspace_id,
        Connector.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    return ConnectorResponse(
        id=str(c.id),
        tenant_id=str(c.tenant_id),
        workspace_id=str(c.workspace_id),
        name=c.name,
        connector_type=c.connector_type,
        status=c.status.value,
        config=c.config,
        sync_schedule=c.sync_schedule,
        last_synced_at=c.last_synced_at.isoformat() if c.last_synced_at else None,
        sync_stats=c.sync_stats,
        last_sync_error=c.last_sync_error,
        created_at=c.created_at.isoformat(),
    )


@router.post("/{connector_id}/test")
async def test_connector_connection(
    workspace_id: uuid.UUID,
    connector_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ping probe testing external connectivity to the SaaS source."""
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.workspace_id == workspace_id,
        Connector.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    try:
        instance = get_connector(c.connector_type, c.config, c.auth_credentials)
        is_ok = await instance.test_connection()
        return {"status": "ok" if is_ok else "failed", "reachable": is_ok}
    except Exception as e:
        return {"status": "error", "reachable": False, "error": str(e)}


@router.post("/{connector_id}/sync")
async def trigger_connector_sync(
    workspace_id: uuid.UUID,
    connector_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an on-demand CDC delta synchronization for the connector."""
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.workspace_id == workspace_id,
        Connector.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    cdc_manager = CdcDeltaSyncManager(db)
    sync_result = await cdc_manager.sync_connector(connector_id)

    return {
        "connector_id": str(connector_id),
        "status": sync_result.status,
        "added": sync_result.added_count,
        "modified": sync_result.modified_count,
        "deleted": sync_result.deleted_count,
        "errors": sync_result.errors,
        "duration_ms": sync_result.duration_ms,
    }


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    workspace_id: uuid.UUID,
    connector_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Connector).where(
        Connector.id == connector_id,
        Connector.workspace_id == workspace_id,
        Connector.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")

    await db.delete(c)
    await db.commit()
    return None


@router.get("/{connector_id}/logs")
async def list_connector_sync_logs(
    workspace_id: uuid.UUID,
    connector_id: uuid.UUID,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ConnectorSyncLog).where(
        ConnectorSyncLog.connector_id == connector_id
    ).order_by(desc(ConnectorSyncLog.started_at)).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        {
            "id": str(log.id),
            "status": log.status.value,
            "documents_synced": log.documents_synced,
            "documents_failed": log.documents_failed,
            "error_summary": log.error_summary,
            "details": log.details,
            "started_at": log.started_at.isoformat(),
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        }
        for log in logs
    ]
