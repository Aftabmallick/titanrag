"""Batch API endpoints — Phase 10.

Provides async batch processing for:
- Batch queries (up to 50 queries per call)
- Batch uploads (up to 100 document URLs)
- Batch deletes (up to 500 document IDs)

Each call returns a job_id immediately. The Celery task processes items
asynchronously and fires a HMAC-signed webhook on completion.

Routes:
  POST /api/v1/workspaces/{workspace_id}/batch/queries   — submit batch query job
  POST /api/v1/workspaces/{workspace_id}/batch/uploads   — submit batch upload job
  POST /api/v1/workspaces/{workspace_id}/batch/delete    — submit batch delete job
  GET  /api/v1/batch/{job_id}                            — poll job status
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import get_current_user
from titan_backend.db.deps import get_db
from titan_backend.db.models.billing import BatchJob, BatchJobStatus, BatchJobType
from titan_backend.db.models.user import User
from titan_backend.db.models.workspaces import Workspace

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Batch API"])

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_BATCH_QUERIES = 50
MAX_BATCH_UPLOADS = 100
MAX_BATCH_DELETES = 500


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BatchQueryItem(BaseModel):
    query: str = Field(..., max_length=4096)
    session_id: str | None = None
    rag_settings_override: dict[str, Any] | None = None


class BatchQueryRequest(BaseModel):
    queries: list[BatchQueryItem] = Field(..., min_length=1, max_length=MAX_BATCH_QUERIES)
    webhook_url: str | None = Field(
        default=None,
        description="HTTPS URL to POST results to on completion (HMAC-signed)",
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://"):
            raise ValueError("webhook_url must use HTTPS")
        return v


class BatchUploadItem(BaseModel):
    url: str = Field(..., description="Publicly accessible URL of the document")
    folder: str | None = None
    acl_groups: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class BatchUploadRequest(BaseModel):
    documents: list[BatchUploadItem] = Field(..., min_length=1, max_length=MAX_BATCH_UPLOADS)
    webhook_url: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://"):
            raise ValueError("webhook_url must use HTTPS")
        return v


class BatchDeleteRequest(BaseModel):
    document_ids: list[UUID] = Field(..., min_length=1, max_length=MAX_BATCH_DELETES)
    webhook_url: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://"):
            raise ValueError("webhook_url must use HTTPS")
        return v


class BatchJobResponse(BaseModel):
    job_id: UUID
    status: str
    job_type: str
    total_items: int
    message: str


class BatchJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    job_type: str
    total_items: int
    completed_items: int
    failed_items: int
    progress_percent: float
    webhook_url: str | None
    webhook_delivered: bool
    results: dict[str, Any]
    error_summary: str | None
    created_at: str
    completed_at: str | None
    eta_seconds: int | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_eta(job: BatchJob) -> int | None:
    """Rough ETA in seconds based on items remaining and job type."""
    if job.status in (BatchJobStatus.COMPLETED, BatchJobStatus.FAILED):
        return 0
    remaining = job.total_items - job.completed_items - job.failed_items
    if remaining <= 0:
        return 0
    # Rough estimates: query=2s, upload=10s, delete=1s per item
    per_item = {"QUERY": 2, "UPLOAD": 10, "DELETE": 1}.get(job.job_type.value, 5)
    return remaining * per_item


async def _create_batch_job(
    db: AsyncSession,
    tenant_id: UUID,
    workspace_id: UUID,
    job_type: BatchJobType,
    total_items: int,
    input_payload: dict[str, Any],
    webhook_url: str | None,
) -> BatchJob:
    """Create a BatchJob record and return it."""
    job = BatchJob(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        job_type=job_type,
        status=BatchJobStatus.PENDING,
        total_items=total_items,
        input_payload=input_payload,
        webhook_url=webhook_url,
    )
    db.add(job)
    await db.flush()  # Get the UUID
    return job


# ---------------------------------------------------------------------------
# Batch Query
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/batch/queries",
    response_model=BatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_batch_queries(
    workspace_id: UUID,
    body: BatchQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchJobResponse:
    """Submit a batch of up to 50 queries for async processing.

    Returns a job_id immediately. Poll GET /api/v1/batch/{job_id} for status.
    On completion, optionally fires a HMAC-signed POST to webhook_url.
    """
    # Validate workspace
    ws = await db.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != current_user.tenant_id or ws.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKSPACE_NOT_FOUND", "message": f"Workspace {workspace_id} not found"},
        )

    job = await _create_batch_job(
        db=db,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        job_type=BatchJobType.QUERY,
        total_items=len(body.queries),
        input_payload={"queries": [q.model_dump() for q in body.queries]},
        webhook_url=body.webhook_url,
    )

    # Dispatch Celery task
    try:
        from titan_workers.tasks.batch_tasks import run_batch_queries

        task = run_batch_queries.apply_async(
            args=[
                str(job.id),
                str(current_user.tenant_id),
                str(workspace_id),
                str(current_user.id),
                [q.model_dump() for q in body.queries],
                body.webhook_url,
            ],
            queue="p1_default",
        )
        job.celery_task_id = task.id
        await db.flush()
    except Exception as exc:
        logger.error("batch_query_dispatch_failed", job_id=str(job.id), error=str(exc))

    await db.commit()

    return BatchJobResponse(
        job_id=job.id,
        status=job.status.value,
        job_type=job.job_type.value,
        total_items=job.total_items,
        message=f"Batch query job created with {job.total_items} queries. Poll job_id for status.",
    )


# ---------------------------------------------------------------------------
# Batch Upload
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/batch/uploads",
    response_model=BatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_batch_uploads(
    workspace_id: UUID,
    body: BatchUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchJobResponse:
    """Submit a batch of up to 100 document URLs for async ingestion.

    Each URL is fetched, parsed, chunked, embedded, and indexed.
    Returns a job_id for polling.
    """
    # Validate workspace
    ws = await db.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != current_user.tenant_id or ws.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKSPACE_NOT_FOUND", "message": f"Workspace {workspace_id} not found"},
        )

    job = await _create_batch_job(
        db=db,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        job_type=BatchJobType.UPLOAD,
        total_items=len(body.documents),
        input_payload={"documents": [d.model_dump() for d in body.documents]},
        webhook_url=body.webhook_url,
    )

    try:
        from titan_workers.tasks.batch_tasks import run_batch_uploads

        task = run_batch_uploads.apply_async(
            args=[
                str(job.id),
                str(current_user.tenant_id),
                str(workspace_id),
                str(current_user.id),
                [d.model_dump() for d in body.documents],
                body.webhook_url,
            ],
            queue="p2_bulk_sync",  # bulk operations go to low-priority queue
        )
        job.celery_task_id = task.id
        await db.flush()
    except Exception as exc:
        logger.error("batch_upload_dispatch_failed", job_id=str(job.id), error=str(exc))

    await db.commit()

    return BatchJobResponse(
        job_id=job.id,
        status=job.status.value,
        job_type=job.job_type.value,
        total_items=job.total_items,
        message=f"Batch upload job created for {job.total_items} documents.",
    )


# ---------------------------------------------------------------------------
# Batch Delete
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/batch/delete",
    response_model=BatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_batch_delete(
    workspace_id: UUID,
    body: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchJobResponse:
    """Submit a batch delete for up to 500 documents.

    Cascades deletion across PostgreSQL, Qdrant, and MinIO.
    """
    # Validate workspace
    ws = await db.get(Workspace, workspace_id)
    if not ws or ws.tenant_id != current_user.tenant_id or ws.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKSPACE_NOT_FOUND", "message": f"Workspace {workspace_id} not found"},
        )

    job = await _create_batch_job(
        db=db,
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        job_type=BatchJobType.DELETE,
        total_items=len(body.document_ids),
        input_payload={"document_ids": [str(d) for d in body.document_ids]},
        webhook_url=body.webhook_url,
    )

    try:
        from titan_workers.tasks.batch_tasks import run_batch_deletes

        task = run_batch_deletes.apply_async(
            args=[
                str(job.id),
                str(current_user.tenant_id),
                str(workspace_id),
                [str(d) for d in body.document_ids],
                body.webhook_url,
            ],
            queue="p1_default",
        )
        job.celery_task_id = task.id
        await db.flush()
    except Exception as exc:
        logger.error("batch_delete_dispatch_failed", job_id=str(job.id), error=str(exc))

    await db.commit()

    return BatchJobResponse(
        job_id=job.id,
        status=job.status.value,
        job_type=job.job_type.value,
        total_items=job.total_items,
        message=f"Batch delete job created for {job.total_items} documents.",
    )


# ---------------------------------------------------------------------------
# Batch Status
# ---------------------------------------------------------------------------


@router.get(
    "/batch/{job_id}",
    response_model=BatchJobStatusResponse,
)
async def get_batch_job_status(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchJobStatusResponse:
    """Poll the status of a batch job.

    Returns detailed progress: items completed, failed, ETA estimate,
    and full results once completed.
    """
    result = await db.execute(
        select(BatchJob).where(
            BatchJob.id == job_id,
            BatchJob.tenant_id == current_user.tenant_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Batch job {job_id} not found"},
        )

    processed = job.completed_items + job.failed_items
    progress = round((processed / job.total_items * 100) if job.total_items > 0 else 0, 1)

    return BatchJobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        job_type=job.job_type.value,
        total_items=job.total_items,
        completed_items=job.completed_items,
        failed_items=job.failed_items,
        progress_percent=progress,
        webhook_url=job.webhook_url,
        webhook_delivered=job.webhook_delivered,
        results=job.results,
        error_summary=job.error_summary,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        eta_seconds=_estimate_eta(job),
    )
