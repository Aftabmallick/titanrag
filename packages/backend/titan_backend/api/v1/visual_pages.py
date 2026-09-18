import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.colpali.entropy_classifier import VisualEntropyClassifier
from titan_backend.colpali.retriever import ColPaliVisualRetriever
from titan_backend.core.dependencies import CurrentUser, get_current_user, get_db
from titan_backend.db.models.visual_pages import VisualPage

router = APIRouter(prefix="/workspaces/{workspace_id}/visual", tags=["colpali-visual"])


class VisualSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(default=5, ge=1, le=20)


class EvaluateEntropyRequest(BaseModel):
    page_number: int
    text: str
    image_count: int = 0
    table_count: int = 0
    drawing_count: int = 0
    image_area_ratio: float = 0.0


@router.get("/documents/{document_id}/pages")
async def list_document_visual_pages(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve all qualified visual diagram/chart pages for a document."""
    stmt = (
        select(VisualPage)
        .where(
            VisualPage.document_id == document_id,
            VisualPage.workspace_id == workspace_id,
            VisualPage.tenant_id == current_user.tenant_id,
        )
        .order_by(VisualPage.page_number)
    )
    res = await db.execute(stmt)
    pages = res.scalars().all()

    return [
        {
            "id": str(p.id),
            "document_id": str(p.document_id),
            "page_number": p.page_number,
            "entropy_score": p.entropy_score,
            "is_visual_qualified": p.is_visual_qualified,
            "image_s3_key": p.rendered_image_s3_key,
            "description": p.description,
        }
        for p in pages
    ]


@router.post("/search")
async def search_visual_knowledge(
    workspace_id: uuid.UUID,
    payload: VisualSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Execute late-interaction visual search across charts, diagrams, and figures."""
    results = await ColPaliVisualRetriever.search_visual_pages(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        query=payload.query,
        limit=payload.limit,
    )
    return {
        "query": payload.query,
        "results_count": len(results),
        "visual_pages": results,
    }


@router.post("/evaluate-entropy")
async def evaluate_page_entropy(
    workspace_id: uuid.UUID,
    payload: EvaluateEntropyRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Test the Gated Visual Entropy Classifier on layout metrics."""
    metrics = VisualEntropyClassifier.evaluate_page(
        page_number=payload.page_number,
        text=payload.text,
        image_count=payload.image_count,
        table_count=payload.table_count,
        drawing_count=payload.drawing_count,
        image_area_ratio=payload.image_area_ratio,
    )
    return {
        "page_number": metrics.page_number,
        "entropy_score": metrics.entropy_score,
        "is_visual_qualified": metrics.is_visual_qualified,
        "text_length": metrics.text_length,
        "threshold": VisualEntropyClassifier.THRESHOLD,
    }
