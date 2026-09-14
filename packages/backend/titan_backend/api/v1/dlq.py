from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import CurrentUser, require_admin
from titan_backend.core.errors import AppException
from titan_backend.db.models.documents import Document, DocumentStatus
from titan_backend.db.models.ingestion import IngestionTask, TaskStatus
from titan_backend.db.models.outbox import ChunkOutbox, OutboxStatus
from titan_backend.db.session import get_db

logger = structlog.get_logger("titanrag.api.dlq")

router = APIRouter(prefix="/admin/dlq", tags=["DLQ Admin"])


class DLQTaskItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    document_id: UUID
    status: str
    stage: str
    error_message: str | None = None
    progress_percent: float


class DLQListResponse(BaseModel):
    failed_ingestion_tasks: list[DLQTaskItem]
    failed_outbox_projections: int


@router.get("", response_model=DLQListResponse)
async def list_failed_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> DLQListResponse:
    # 1. Fetch failed ingestion tasks for tenant
    stmt_tasks = select(IngestionTask).where(
        IngestionTask.tenant_id == current_user.tenant_id,
        IngestionTask.status == TaskStatus.FAILED,
    )
    failed_tasks = (await db.execute(stmt_tasks)).scalars().all()

    # 2. Count failed outbox projection records
    stmt_outbox = select(ChunkOutbox).where(
        ChunkOutbox.tenant_id == current_user.tenant_id,
        ChunkOutbox.status == OutboxStatus.FAILED,
    )
    failed_outbox_count = len((await db.execute(stmt_outbox)).scalars().all())

    return DLQListResponse(
        failed_ingestion_tasks=[DLQTaskItem.model_validate(t) for t in failed_tasks],
        failed_outbox_projections=failed_outbox_count,
    )


@router.post("/{task_id}/retry", status_code=200)
async def retry_failed_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    stmt = select(IngestionTask).where(
        IngestionTask.id == task_id,
        IngestionTask.tenant_id == current_user.tenant_id,
    )
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise AppException(message="Task not found in DLQ.", status_code=404, error_code="DLQ_TASK_NOT_FOUND")

    # Reset task status to QUEUED and document status to PROCESSING
    task.status = TaskStatus.QUEUED
    task.error_message = None
    await db.execute(
        update(Document).where(Document.id == task.document_id).values(status=DocumentStatus.PROCESSING)
    )
    # Also retry any failed outbox items for this document
    await db.execute(
        update(ChunkOutbox)
        .where(
            ChunkOutbox.tenant_id == current_user.tenant_id,
            ChunkOutbox.status == OutboxStatus.FAILED,
        )
        .values(status=OutboxStatus.PENDING, attempts=0, last_error=None)
    )
    await db.commit()
    logger.info("dlq_task_retried", task_id=str(task_id))
    return {"status": "requeued", "task_id": str(task_id)}


@router.delete("/{task_id}/discard", status_code=200)
async def discard_failed_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    stmt = select(IngestionTask).where(
        IngestionTask.id == task_id,
        IngestionTask.tenant_id == current_user.tenant_id,
    )
    task = (await db.execute(stmt)).scalars().first()
    if not task:
        raise AppException(message="Task not found in DLQ.", status_code=404, error_code="DLQ_TASK_NOT_FOUND")

    # Mark document as ARCHIVED and task as discarded
    await db.execute(
        update(Document).where(Document.id == task.document_id).values(status=DocumentStatus.ARCHIVED)
    )
    await db.delete(task)
    await db.commit()
    logger.info("dlq_task_discarded", task_id=str(task_id))
    return {"status": "discarded", "task_id": str(task_id)}
