from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.rag_settings import RAGSettingsResponse, RAGSettingsUpdate
from titan_backend.core.dependencies import CurrentUser, get_current_user, require_permission
from titan_backend.core.logging import logger
from titan_backend.core.rbac import Permission
from titan_backend.db.models.settings import RAGSettings
from titan_backend.db.session import get_db
from titan_backend.services.retrieval.semantic_cache import semantic_cache

router = APIRouter(prefix="/workspaces/{workspace_id}/settings", tags=["RAG Settings"])


@router.get("", response_model=RAGSettingsResponse)
async def get_rag_settings(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SEARCH)),
) -> RAGSettingsResponse:
    """Get active RAG configuration for the specified workspace.

    Auto-provisions defaults if not present.
    """
    stmt = select(RAGSettings).where(
        RAGSettings.workspace_id == workspace_id,
        RAGSettings.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    settings_obj = res.scalar_one_or_none()

    if not settings_obj:
        logger.info("auto_provisioning_rag_settings", workspace_id=str(workspace_id))
        settings_obj = RAGSettings(
            tenant_id=current_user.tenant_id,
            workspace_id=workspace_id,
            retrieval_mode="HYBRID",
            dense_weight=0.7,
            sparse_weight=0.3,
            top_k=20,
            rerank_top_k=5,
            score_threshold=0.40,
            context_window_strategy="HIERARCHICAL",
            parent_context_enabled=False,
            hyde_enabled=False,
            semantic_cache_enabled=True,
            cache_cosine_threshold=0.95,
            cache_ttl_seconds=86400,
            system_prompt_override=None,
        )
        db.add(settings_obj)
        await db.commit()
        await db.refresh(settings_obj)

    return RAGSettingsResponse(
        id=settings_obj.id,
        tenant_id=settings_obj.tenant_id,
        workspace_id=settings_obj.workspace_id,
        retrieval_mode=settings_obj.retrieval_mode,
        dense_weight=settings_obj.dense_weight,
        sparse_weight=settings_obj.sparse_weight,
        top_k=settings_obj.top_k,
        rerank_top_k=settings_obj.rerank_top_k,
        score_threshold=settings_obj.score_threshold,
        context_window_strategy=settings_obj.context_window_strategy,
        parent_context_enabled=getattr(settings_obj, "parent_context_enabled", False) or False,
        hyde_enabled=getattr(settings_obj, "hyde_enabled", False) or False,
        semantic_cache_enabled=getattr(settings_obj, "semantic_cache_enabled", True) if getattr(settings_obj, "semantic_cache_enabled", None) is not None else True,
        cache_cosine_threshold=getattr(settings_obj, "cache_cosine_threshold", 0.95) or 0.95,
        cache_ttl_seconds=getattr(settings_obj, "cache_ttl_seconds", 86400) or 86400,
        system_prompt_override=getattr(settings_obj, "system_prompt_override", None),
        created_at=settings_obj.created_at.isoformat() if settings_obj.created_at else "2026-09-14T00:00:00Z",
        updated_at=settings_obj.updated_at.isoformat() if settings_obj.updated_at else "2026-09-14T00:00:00Z",
    )


@router.put("", response_model=RAGSettingsResponse, status_code=status.HTTP_200_OK)
async def update_rag_settings(
    workspace_id: UUID,
    payload: RAGSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.MANAGE_SETTINGS)),
) -> RAGSettingsResponse:
    """Update RAG retrieval, reranking, and cache configuration with immediate effect."""
    stmt = select(RAGSettings).where(
        RAGSettings.workspace_id == workspace_id,
        RAGSettings.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    settings_obj = res.scalar_one_or_none()

    if not settings_obj:
        settings_obj = RAGSettings(
            tenant_id=current_user.tenant_id,
            workspace_id=workspace_id,
        )
        db.add(settings_obj)

    update_dict = payload.model_dump(exclude_unset=True)
    if "retrieval_mode" in update_dict and update_dict["retrieval_mode"] is not None:
        settings_obj.retrieval_mode = update_dict["retrieval_mode"].value

    for key, value in update_dict.items():
        if key != "retrieval_mode" and hasattr(settings_obj, key):
            setattr(settings_obj, key, value)

    await db.commit()
    await db.refresh(settings_obj)

    # Invalidate semantic cache for this workspace
    await semantic_cache.invalidate_workspace(current_user.tenant_id, workspace_id)

    logger.info("rag_settings_updated", workspace_id=str(workspace_id), user_id=str(current_user.user_id))

    return RAGSettingsResponse(
        id=settings_obj.id,
        tenant_id=settings_obj.tenant_id,
        workspace_id=settings_obj.workspace_id,
        retrieval_mode=settings_obj.retrieval_mode,
        dense_weight=settings_obj.dense_weight,
        sparse_weight=settings_obj.sparse_weight,
        top_k=settings_obj.top_k,
        rerank_top_k=settings_obj.rerank_top_k,
        score_threshold=settings_obj.score_threshold,
        context_window_strategy=settings_obj.context_window_strategy,
        parent_context_enabled=getattr(settings_obj, "parent_context_enabled", False) or False,
        hyde_enabled=getattr(settings_obj, "hyde_enabled", False) or False,
        semantic_cache_enabled=getattr(settings_obj, "semantic_cache_enabled", True) if getattr(settings_obj, "semantic_cache_enabled", None) is not None else True,
        cache_cosine_threshold=getattr(settings_obj, "cache_cosine_threshold", 0.95) or 0.95,
        cache_ttl_seconds=getattr(settings_obj, "cache_ttl_seconds", 86400) or 86400,
        system_prompt_override=getattr(settings_obj, "system_prompt_override", None),
        created_at=settings_obj.created_at.isoformat() if settings_obj.created_at else "2026-09-14T00:00:00Z",
        updated_at=settings_obj.updated_at.isoformat() if settings_obj.updated_at else "2026-09-14T00:00:00Z",
    )
