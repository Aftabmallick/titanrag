import re
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.plugins import (
    PluginCreatedResponse,
    PluginCreateRequest,
    PluginExecutionLogResponse,
    PluginPingResponse,
    PluginResponse,
    PluginUpdateRequest,
)
from titan_backend.core.dependencies import CurrentUser, get_current_user, require_permission
from titan_backend.core.rbac import Permission
from titan_backend.db.models.plugin import Plugin, PluginExecutionLog
from titan_backend.db.session import get_db
from titan_backend.services.plugins.dispatcher import PluginDispatcher
from titan_backend.services.plugins.signer import WebhookSigner

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/plugins", tags=["Plugins & Micro-Hooks"])


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"


def _serialize_plugin(plugin: Plugin) -> PluginResponse:
    return PluginResponse(
        id=plugin.id,
        tenant_id=plugin.tenant_id,
        workspace_id=plugin.workspace_id,
        name=plugin.name,
        slug=plugin.slug,
        description=plugin.description,
        version=plugin.version,
        endpoint_url=plugin.endpoint_url,
        webhook_secret_masked=_mask_secret(plugin.webhook_secret),
        hooks=plugin.hooks or [],
        timeout_ms=plugin.timeout_ms,
        retry_count=plugin.retry_count,
        is_active=plugin.is_active,
        health_status=plugin.health_status,
        last_ping_at=plugin.last_ping_at,
        failure_count=plugin.failure_count,
        circuit_tripped=plugin.circuit_tripped,
        created_at=plugin.created_at,
        updated_at=plugin.updated_at,
    )


def _generate_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\-_]", "-", name.lower()).strip("-")
    return cleaned[:80] or "plugin"


@router.get("", response_model=list[PluginResponse])
async def list_plugins(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> list[PluginResponse]:
    """List all registered webhook micro-hook plugins for the workspace."""
    stmt = (
        select(Plugin)
        .where(
            Plugin.workspace_id == workspace_id,
            Plugin.tenant_id == current_user.tenant_id,
        )
        .order_by(Plugin.created_at.desc())
    )
    res = await db.execute(stmt)
    plugins = res.scalars().all()
    return [_serialize_plugin(p) for p in plugins]


@router.post("", response_model=PluginCreatedResponse, status_code=status.HTTP_201_CREATED)
async def register_plugin(
    workspace_id: UUID,
    request: PluginCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.MANAGE_SETTINGS)),
) -> PluginCreatedResponse:
    """
    Register a new webhook micro-hook plugin.
    Generates a secure 256-bit HMAC secret and returns it in the response (displayed once).
    """
    slug = request.slug or _generate_slug(request.name)

    # Check for duplicate slug within workspace
    existing_stmt = select(Plugin).where(
        Plugin.workspace_id == workspace_id,
        Plugin.slug == slug,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A plugin with slug '{slug}' already exists in this workspace",
        )

    secret = request.webhook_secret or WebhookSigner.generate_secret()
    hook_strings = [h.value for h in request.hooks]

    plugin = Plugin(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        name=request.name,
        slug=slug,
        description=request.description,
        version=request.version,
        endpoint_url=str(request.endpoint_url),
        webhook_secret=secret,
        hooks=hook_strings,
        timeout_ms=request.timeout_ms,
        retry_count=request.retry_count,
        is_active=request.is_active,
    )
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)

    logger.info(
        "plugin_registered",
        workspace_id=str(workspace_id),
        plugin_id=str(plugin.id),
        slug=slug,
        hooks=hook_strings,
    )

    base = _serialize_plugin(plugin)
    return PluginCreatedResponse(
        **base.model_dump(),
        webhook_secret=secret,
    )


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(
    workspace_id: UUID,
    plugin_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> PluginResponse:
    """Retrieve details for a specific registered plugin."""
    stmt = select(Plugin).where(
        Plugin.id == plugin_id,
        Plugin.workspace_id == workspace_id,
        Plugin.tenant_id == current_user.tenant_id,
    )
    plugin = (await db.execute(stmt)).scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")
    return _serialize_plugin(plugin)


@router.patch("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(
    workspace_id: UUID,
    plugin_id: UUID,
    request: PluginUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.MANAGE_SETTINGS)),
) -> PluginResponse:
    """Update plugin configuration, enabled hooks, timeout, or active status."""
    stmt = select(Plugin).where(
        Plugin.id == plugin_id,
        Plugin.workspace_id == workspace_id,
        Plugin.tenant_id == current_user.tenant_id,
    )
    plugin = (await db.execute(stmt)).scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    if request.name is not None:
        plugin.name = request.name
    if request.description is not None:
        plugin.description = request.description
    if request.endpoint_url is not None:
        plugin.endpoint_url = str(request.endpoint_url)
    if request.webhook_secret is not None:
        plugin.webhook_secret = request.webhook_secret
    if request.hooks is not None:
        plugin.hooks = [h.value for h in request.hooks]
    if request.timeout_ms is not None:
        plugin.timeout_ms = request.timeout_ms
    if request.retry_count is not None:
        plugin.retry_count = request.retry_count
    if request.is_active is not None:
        plugin.is_active = request.is_active

    await db.commit()
    await db.refresh(plugin)
    return _serialize_plugin(plugin)


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_plugin(
    workspace_id: UUID,
    plugin_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.MANAGE_SETTINGS)),
) -> None:
    """Deregister and permanently delete a plugin and its execution history."""
    stmt = select(Plugin).where(
        Plugin.id == plugin_id,
        Plugin.workspace_id == workspace_id,
        Plugin.tenant_id == current_user.tenant_id,
    )
    plugin = (await db.execute(stmt)).scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    await db.delete(plugin)
    await db.commit()
    logger.info("plugin_deregistered", plugin_id=str(plugin_id), workspace_id=str(workspace_id))


@router.post("/{plugin_id}/ping", response_model=PluginPingResponse)
async def ping_plugin(
    workspace_id: UUID,
    plugin_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.MANAGE_SETTINGS)),
) -> PluginPingResponse:
    """
    Send an immediate test probe to the plugin's webhook endpoint to verify
    connectivity, latency, and HMAC-SHA256 signature verification.
    """
    stmt = select(Plugin).where(
        Plugin.id == plugin_id,
        Plugin.workspace_id == workspace_id,
        Plugin.tenant_id == current_user.tenant_id,
    )
    plugin = (await db.execute(stmt)).scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found")

    dispatcher = PluginDispatcher(db=db)
    res = await dispatcher.ping_probe(plugin)

    return PluginPingResponse(
        success=res.success,
        status_code=res.status_code,
        latency_ms=res.latency_ms,
        error=res.error,
        circuit_tripped=res.circuit_tripped,
    )


@router.get("/{plugin_id}/logs", response_model=list[PluginExecutionLogResponse])
async def list_plugin_logs(
    workspace_id: UUID,
    plugin_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> list[PluginExecutionLogResponse]:
    """Query recent execution logs for a registered plugin."""
    stmt = (
        select(PluginExecutionLog)
        .where(
            PluginExecutionLog.plugin_id == plugin_id,
            PluginExecutionLog.workspace_id == workspace_id,
            PluginExecutionLog.tenant_id == current_user.tenant_id,
        )
        .order_by(desc(PluginExecutionLog.timestamp))
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [PluginExecutionLogResponse.model_validate(log) for log in logs]
