from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import CurrentUser, get_current_user
from titan_backend.db.models.promptops import PromptEnvironment, PromptTemplate, PromptVersion
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db
from titan_backend.services.promptops.diff import compute_prompt_diff
from titan_backend.services.promptops.engine import PromptOpsEngine

router = APIRouter(prefix="/workspaces/{workspace_id}/prompts", tags=["PromptOps"])


class CreatePromptVersionRequest(BaseModel):
    content: str = Field(..., description="Jinja2 template content")
    name: str | None = None
    commit_message: str | None = None
    environment: PromptEnvironment = PromptEnvironment.DEV
    input_schema: dict[str, Any] = Field(default_factory=dict)


class PromotePromptRequest(BaseModel):
    version_number: int
    target_environment: PromptEnvironment
    force: bool = Field(default=False, description="Bypass promotion regression gates with audit record")


@router.get("")
async def list_workspace_prompts(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all prompt templates for a workspace with their latest/active versions."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    templates_stmt = select(PromptTemplate).where(PromptTemplate.workspace_id == workspace_id)
    templates = (await session.execute(templates_stmt)).scalars().all()

    result = []
    for t in templates:
        active_versions_stmt = select(PromptVersion).where(
            PromptVersion.template_id == t.id,
            PromptVersion.is_active,
        )
        active_versions = (await session.execute(active_versions_stmt)).scalars().all()

        result.append(
            {
                "id": str(t.id),
                "slug": t.slug,
                "name": t.name,
                "description": t.description,
                "active_versions": [
                    {
                        "version_number": v.version_number,
                        "environment": v.environment.value,
                        "token_count": v.token_count_estimate,
                        "created_at": v.created_at.isoformat(),
                    }
                    for v in active_versions
                ],
            }
        )

    return {"templates": result}


@router.get("/{slug}/versions")
async def list_prompt_versions(
    workspace_id: UUID,
    slug: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List version history for a given prompt slug."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    tmpl_stmt = select(PromptTemplate).where(
        PromptTemplate.workspace_id == workspace_id,
        PromptTemplate.slug == slug,
    )
    tmpl = (await session.execute(tmpl_stmt)).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{slug}' not found")

    ver_stmt = (
        select(PromptVersion).where(PromptVersion.template_id == tmpl.id).order_by(PromptVersion.version_number.desc())
    )
    versions = (await session.execute(ver_stmt)).scalars().all()

    return {
        "template": {"id": str(tmpl.id), "slug": tmpl.slug, "name": tmpl.name},
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "content": v.content,
                "environment": v.environment.value,
                "commit_message": v.commit_message,
                "is_active": v.is_active,
                "token_count": v.token_count_estimate,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
    }


@router.post("/{slug}/versions", status_code=status.HTTP_201_CREATED)
async def create_prompt_version(
    workspace_id: UUID,
    slug: str,
    req: CreatePromptVersionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new version of a prompt template in DEV environment."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        ver = await PromptOpsEngine.create_version(
            session=session,
            tenant_id=current_user.tenant_id,
            workspace_id=workspace_id,
            slug=slug,
            content=req.content,
            name=req.name,
            author_id=current_user.id,
            commit_message=req.commit_message,
            environment=req.environment,
            input_schema=req.input_schema,
        )
        return {
            "id": str(ver.id),
            "version_number": ver.version_number,
            "environment": ver.environment.value,
            "token_count": ver.token_count_estimate,
            "message": "Prompt version created successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/{slug}/promote")
async def promote_prompt_version(
    workspace_id: UUID,
    slug: str,
    req: PromotePromptRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Promote a prompt version to STAGING or PROD with automated cache invalidation."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    tmpl_stmt = select(PromptTemplate).where(
        PromptTemplate.workspace_id == workspace_id,
        PromptTemplate.slug == slug,
    )
    tmpl = (await session.execute(tmpl_stmt)).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{slug}' not found")

    try:
        promoted = await PromptOpsEngine.promote_version(
            session=session,
            template_id=tmpl.id,
            version_number=req.version_number,
            target_environment=req.target_environment,
            force=req.force,
        )
        return {
            "slug": slug,
            "version_number": promoted.version_number,
            "environment": promoted.environment.value,
            "is_active": promoted.is_active,
            "message": f"Successfully promoted version {promoted.version_number} to {promoted.environment.value}",
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/{slug}/rollback")
async def rollback_prompt(
    workspace_id: UUID,
    slug: str,
    environment: PromptEnvironment = Query(PromptEnvironment.PROD),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Roll back active prompt version to the previous revision."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    tmpl_stmt = select(PromptTemplate).where(
        PromptTemplate.workspace_id == workspace_id,
        PromptTemplate.slug == slug,
    )
    tmpl = (await session.execute(tmpl_stmt)).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{slug}' not found")

    try:
        active = await PromptOpsEngine.rollback_version(
            session=session,
            template_id=tmpl.id,
            target_environment=environment,
        )
        return {
            "slug": slug,
            "active_version": active.version_number,
            "environment": active.environment.value,
            "message": f"Rolled back to version {active.version_number}",
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/{slug}/diff")
async def diff_prompt_versions(
    workspace_id: UUID,
    slug: str,
    v1: int = Query(..., description="First version number"),
    v2: int = Query(..., description="Second version number"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Calculate token and unified line diff between two prompt versions."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    tmpl_stmt = select(PromptTemplate).where(
        PromptTemplate.workspace_id == workspace_id,
        PromptTemplate.slug == slug,
    )
    tmpl = (await session.execute(tmpl_stmt)).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt '{slug}' not found")

    v1_stmt = select(PromptVersion).where(PromptVersion.template_id == tmpl.id, PromptVersion.version_number == v1)
    v2_stmt = select(PromptVersion).where(PromptVersion.template_id == tmpl.id, PromptVersion.version_number == v2)

    ver1 = (await session.execute(v1_stmt)).scalar_one_or_none()
    ver2 = (await session.execute(v2_stmt)).scalar_one_or_none()

    if not ver1 or not ver2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both versions not found")

    diff_data = compute_prompt_diff(ver1.content, ver2.content)
    return {
        "slug": slug,
        "v1": v1,
        "v2": v2,
        **diff_data,
    }
