import asyncio
import os
from typing import Any
from uuid import UUID

import structlog
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from titan_backend.core.config import settings
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
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False,
    )


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
) -> dict[str, Any]:
    # 1. Download source file from MinIO
    minio_client = _get_minio_client()
    try:
        response = await asyncio.to_thread(
            minio_client.get_object,
            bucket_name=MINIO_BUCKET,
            object_name=storage_path,
        )
        file_bytes = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        logger.error("minio_download_failed", storage_path=storage_path, error=str(e))
        raise e

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
    default_retry_delay=10,
    queue="p1_default",
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
) -> dict[str, Any]:
    logger.info("processing_document_task_received", document_id=document_id, filename=filename)
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
            )
        )
    except Exception as exc:
        logger.error("ingestion_task_error", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc) from exc
