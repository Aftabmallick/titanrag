import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
import urllib3
from minio import Minio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from titan_backend.core.config import settings
from titan_backend.db.models.documents import Document, DocumentStatus
from titan_backend.db.models.ingestion import IngestionTask, TaskStatus

from titan_workers.base_task import TracedTask
from titan_workers.celery_app import celery_app
from titan_workers.pipeline.orchestrator import IngestionPipelineOrchestrator

logger = structlog.get_logger("titanrag.tasks.ingestion")

DATABASE_URL = settings.get_database_url()
MINIO_ENDPOINT = settings.MINIO_ENDPOINT
MINIO_ROOT_USER = settings.MINIO_ROOT_USER
MINIO_ROOT_PASSWORD = settings.MINIO_ROOT_PASSWORD
MINIO_BUCKET = settings.MINIO_BUCKET


def _get_minio_client() -> Minio:
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=5.0, read=60.0),
        maxsize=50,
        retries=urllib3.Retry(total=3, backoff_factor=0.2),
    )
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False,
        http_client=http_client,
    )


async def _record_terminal_failure(
    tenant_id: str,
    workspace_id: str,
    document_id: str,
    filename: str,
    mime_type: str,
    error: str,
    retries: int = 3,
) -> None:
    """Record a terminal failure to the database (DLQ), ensuring Document and IngestionTask are marked FAILED."""
    try:
        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            now_iso = datetime.now(UTC).isoformat()
            failure_meta = {
                "last_error": error,
                "failed_at": now_iso,
                "retries": retries,
                "error_type": "DLQ_INGESTION_FAILURE",
                "filename": filename,
                "mime_type": mime_type,
            }
            await session.execute(
                update(Document)
                .where(Document.id == UUID(document_id))
                .values(
                    status=DocumentStatus.FAILED,
                    meta=failure_meta,
                )
            )
            await session.execute(
                update(IngestionTask)
                .where(IngestionTask.document_id == UUID(document_id))
                .values(
                    status=TaskStatus.FAILED,
                    error_message=f"[DLQ Exhausted after {retries} retries]: {error}",
                )
            )
            await session.commit()
        await engine.dispose()
    except Exception as e:
        logger.error("record_terminal_failure_failed", error=str(e), document_id=document_id)


async def _execute_ingestion(
    tenant_id: str,
    workspace_id: str,
    document_id: str,
    storage_path: str,
    filename: str,
    mime_type: str,
    redaction_mode: str = "REPLACE",
    webhook_url: str | None = None,
    webhook_secret: str | None = None,
    bucket_name: str | None = None,
) -> dict[str, Any]:
    # 0. Set status to PROCESSING in DB
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            update(Document).where(Document.id == UUID(document_id)).values(status=DocumentStatus.PROCESSING)
        )
        await session.execute(
            update(IngestionTask)
            .where(IngestionTask.document_id == UUID(document_id))
            .values(status=TaskStatus.PROCESSING, stage="DOWNLOADING", progress_percent=0.05)
        )
        await session.commit()
    await engine.dispose()

    # 1. Download source file from MinIO
    minio_client = _get_minio_client()
    target_bucket = bucket_name or MINIO_BUCKET
    file_bytes = None

    for b in [target_bucket, MINIO_BUCKET, "titan-documents-us-east"]:
        try:
            response = await asyncio.to_thread(
                minio_client.get_object,
                bucket_name=b,
                object_name=storage_path,
            )
            file_bytes = response.read()
            response.close()
            response.release_conn()
            break
        except Exception:
            continue

    if file_bytes is None:
        logger.error("minio_download_failed", storage_path=storage_path, attempted_bucket=target_bucket)
        raise RuntimeError(f"Source file {storage_path} not found in MinIO bucket {target_bucket}")

    from titan_backend.clients.qdrant_client import TenantIngestionSemaphore

    sem = TenantIngestionSemaphore(tenant_id=tenant_id, max_concurrent=5)
    async with sem as acquired:
        if not acquired:
            logger.warning("tenant_semaphore_saturated_retrying", tenant_id=tenant_id)
            raise RuntimeError("Tenant ingestion concurrency limit reached. Re-queueing task.")

        # 2. Setup async DB session and run orchestrator
        engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        orchestrator = IngestionPipelineOrchestrator(minio_client=minio_client)
        async with session_factory() as session:
            result = await orchestrator.run_pipeline(
                db=session,
                tenant_id=UUID(tenant_id),
                workspace_id=UUID(workspace_id),
                document_id=UUID(document_id),
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type,
                redaction_mode=redaction_mode,
                webhook_url=webhook_url,
                webhook_secret=webhook_secret,
            )

        await engine.dispose()
        return result


@celery_app.task(
    base=TracedTask,
    name="titan_workers.tasks.ingestion.process_document_pipeline",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="p2_bulk_sync",
)
def process_document_pipeline(
    self: Any,
    tenant_id: str,
    workspace_id: str,
    document_id: str,
    storage_path: str,
    filename: str,
    mime_type: str,
    redaction_mode: str = "REPLACE",
    webhook_url: str | None = None,
    webhook_secret: str | None = None,
    bucket_name: str | None = None,
) -> dict[str, Any]:
    retries = self.request.retries
    logger.info("processing_document_task_received", document_id=document_id, filename=filename, retry=retries)
    try:
        return asyncio.run(
            _execute_ingestion(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                document_id=document_id,
                storage_path=storage_path,
                filename=filename,
                mime_type=mime_type,
                redaction_mode=redaction_mode,
                webhook_url=webhook_url,
                webhook_secret=webhook_secret,
                bucket_name=bucket_name,
            )
        )
    except Exception as exc:
        logger.error(
            "ingestion_task_error",
            document_id=document_id,
            error=str(exc),
            retry=retries,
            max_retries=self.max_retries,
        )
        if retries < self.max_retries:
            delay = 30 * (2**retries)
            raise self.retry(exc=exc, countdown=delay) from exc
        else:
            logger.critical(
                "ingestion_task_dlq_terminal_failure",
                document_id=document_id,
                error=str(exc),
                retries=retries,
            )
            asyncio.run(
                _record_terminal_failure(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    filename=filename,
                    mime_type=mime_type,
                    error=str(exc),
                    retries=retries,
                )
            )
            raise exc
