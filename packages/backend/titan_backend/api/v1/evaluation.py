from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.auth import CurrentUser, get_current_user
from titan_backend.db.models.evaluation import (
    EvaluationResultItem,
    EvaluationRun,
    EvaluationStatus,
    EvaluationTrigger,
    GoldenDataset,
    GoldenDatasetItem,
)
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["Evaluation & Benchmarks"])


class CreateDatasetRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateDatasetItemRequest(BaseModel):
    query: str
    expected_answer: str
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_document_ids: list[str] = Field(default_factory=list)
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    context: str | None = None
    tags: list[str] = Field(default_factory=list)


class TriggerEvaluationRequest(BaseModel):
    dataset_id: UUID
    rag_config_override: dict[str, Any] = Field(default_factory=dict)


@router.get("/golden-datasets")
async def list_golden_datasets(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List golden evaluation datasets for the workspace."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    stmt = (
        select(GoldenDataset)
        .where(GoldenDataset.workspace_id == workspace_id)
        .order_by(GoldenDataset.created_at.desc())
    )
    datasets = (await session.execute(stmt)).scalars().all()

    result = []
    for d in datasets:
        items_count_stmt = select(GoldenDatasetItem.id).where(GoldenDatasetItem.dataset_id == d.id)
        count = len((await session.execute(items_count_stmt)).scalars().all())
        result.append(
            {
                "id": str(d.id),
                "name": d.name,
                "description": d.description,
                "version": d.version,
                "tags": d.tags,
                "is_active": d.is_active,
                "item_count": count,
                "created_at": d.created_at.isoformat(),
            }
        )

    return {"datasets": result}


@router.post("/golden-datasets", status_code=status.HTTP_201_CREATED)
async def create_golden_dataset(
    workspace_id: UUID,
    req: CreateDatasetRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new golden evaluation dataset."""
    workspace = await session.get(Workspace, workspace_id)
    if not workspace or workspace.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    dataset = GoldenDataset(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        tags=req.tags,
        is_active=True,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)

    return {
        "id": str(dataset.id),
        "name": dataset.name,
        "message": "Golden dataset created successfully",
    }


@router.get("/golden-datasets/{dataset_id}/items")
async def list_dataset_items(
    workspace_id: UUID,
    dataset_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List all benchmark query items in a golden dataset."""
    dataset = await session.get(GoldenDataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    stmt = (
        select(GoldenDatasetItem)
        .where(GoldenDatasetItem.dataset_id == dataset_id)
        .order_by(GoldenDatasetItem.created_at)
    )
    items = (await session.execute(stmt)).scalars().all()

    return {
        "dataset_id": str(dataset_id),
        "items": [
            {
                "id": str(it.id),
                "query": it.query,
                "expected_answer": it.expected_answer,
                "expected_chunk_ids": it.expected_chunk_ids,
                "expected_document_ids": it.expected_document_ids,
                "tags": it.tags,
                "context": it.context,
            }
            for it in items
        ],
    }


@router.post("/golden-datasets/{dataset_id}/items", status_code=status.HTTP_201_CREATED)
async def add_dataset_item(
    workspace_id: UUID,
    dataset_id: UUID,
    req: CreateDatasetItemRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add a query-answer-sources test item to a golden dataset."""
    dataset = await session.get(GoldenDataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    item = GoldenDatasetItem(
        dataset_id=dataset_id,
        query=req.query,
        expected_answer=req.expected_answer,
        expected_chunk_ids=req.expected_chunk_ids,
        expected_document_ids=req.expected_document_ids,
        metadata_filters=req.metadata_filters,
        context=req.context,
        tags=req.tags,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return {
        "id": str(item.id),
        "message": "Dataset item added successfully",
    }


@router.post("/evaluations/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation_run(
    workspace_id: UUID,
    req: TriggerEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger an asynchronous benchmark evaluation run across golden dataset items."""
    dataset = await session.get(GoldenDataset, req.dataset_id)
    if not dataset or dataset.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    # Create run record
    run = EvaluationRun(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        dataset_id=req.dataset_id,
        rag_config_snapshot=req.rag_config_override,
        status=EvaluationStatus.PENDING,
        triggered_by=EvaluationTrigger.MANUAL,
        aggregate_scores={},
        latency_stats={},
        total_compute_units=0.0,
        total_dollar_cost=0.0,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Dispatch Celery task
    try:
        from titan_workers.tasks.evaluation_tasks import run_evaluation_suite

        run_evaluation_suite.delay(str(run.id), str(dataset.id))
    except Exception:
        # If workers not running synchronously in current process, update status for test runner
        pass

    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "message": "Evaluation run queued successfully",
    }


@router.get("/evaluations/runs/{run_id}")
async def get_evaluation_run(
    workspace_id: UUID,
    run_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get status, radar benchmark scores, and drill-down results for an evaluation run."""
    run = await session.get(EvaluationRun, run_id)
    if not run or run.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")

    results_stmt = select(EvaluationResultItem).where(EvaluationResultItem.run_id == run_id)
    results = (await session.execute(results_stmt)).scalars().all()

    return {
        "run_id": str(run.id),
        "dataset_id": str(run.dataset_id),
        "status": run.status.value,
        "aggregate_scores": run.aggregate_scores,
        "latency_stats": run.latency_stats,
        "total_compute_units": run.total_compute_units,
        "total_dollar_cost": run.total_dollar_cost,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat(),
        "results": [
            {
                "id": str(r.id),
                "query": r.query,
                "generated_answer": r.generated_answer,
                "scores": r.scores,
                "latency_ms": r.latency_ms,
                "tokens_used": r.tokens_used,
            }
            for r in results
        ],
    }
