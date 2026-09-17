from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import CurrentUser, get_current_user
from titan_backend.api.v1.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackTriageRequest,
)
from titan_backend.db.models.feedback import FeedbackTriageStatus
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db
from titan_backend.services.feedback_service import FeedbackService

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["Feedback & LLMOps"])


@router.post(
    "/chat-messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_message_feedback(
    workspace_id: UUID,
    message_id: UUID,
    req: FeedbackCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Submit rating, comments, and granular citation errors for an assistant response."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        feedback = await FeedbackService.create_feedback(
            session=session,
            tenant_id=current_user.tenant_id,
            workspace_id=workspace_id,
            message_id=message_id,
            user_id=current_user.id,
            rating=req.rating,
            comment=req.comment,
            corrected_answer=req.corrected_answer,
            citation_issues=[c.model_dump() for c in req.citation_issues],
        )
        return feedback
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/feedback")
async def list_workspace_feedback(
    workspace_id: UUID,
    rating: int | None = Query(None, description="1 for positive, -1 for negative"),
    triage_status: FeedbackTriageStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List and filter feedback records with aggregate satisfaction scores."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    items, total, stats = await FeedbackService.list_feedback(
        session=session,
        workspace_id=workspace_id,
        rating=rating,
        triage_status=triage_status,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [FeedbackResponse.model_validate(item).model_dump() for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "statistics": stats,
    }


@router.patch("/feedback/{feedback_id}/triage", response_model=FeedbackResponse)
async def update_feedback_triage(
    workspace_id: UUID,
    feedback_id: UUID,
    req: FeedbackTriageRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Triage feedback for evaluation flywheel (NEW -> TRIAGED -> PROMOTED_TO_GOLDEN | IGNORED)."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        return await FeedbackService.update_triage_status(
            session=session,
            feedback_id=feedback_id,
            workspace_id=workspace_id,
            status=req.triage_status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/feedback/{feedback_id}/promote-to-golden", status_code=status.HTTP_201_CREATED)
async def promote_feedback_to_golden_dataset(
    workspace_id: UUID,
    feedback_id: UUID,
    dataset_id: UUID | None = Query(None, description="Optional target golden dataset UUID"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """1-Click promote a negative or corrected user feedback interaction into a golden dataset item."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    from titan_backend.services.flywheel.triage import FlywheelTriageService

    try:
        item = await FlywheelTriageService.promote_feedback_to_golden(
            session=session,
            workspace_id=workspace_id,
            feedback_id=feedback_id,
            dataset_id=dataset_id,
        )
        return {
            "message": "Feedback successfully promoted to golden evaluation dataset",
            "golden_dataset_item_id": str(item.id),
            "dataset_id": str(item.dataset_id),
            "query": item.query,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

