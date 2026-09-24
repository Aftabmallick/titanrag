"""Celery Tasks for Batch API — Phase 10.

Tasks:
- run_batch_queries   — process 1..50 RAG queries sequentially
- run_batch_uploads   — ingest 1..100 document URLs via existing pipeline
- run_batch_deletes   — cascade-delete 1..500 documents
- deliver_batch_webhook — HMAC-signed webhook delivery with retry
- purge_sandbox_sessions — hourly cleanup of expired ephemeral sessions
- seed_sandbox_demo_workspace — provision demo docs for a new sandbox session
- report_monthly_cu_to_stripe — monthly CU metering cron
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, update

from titan_workers.celery_app import celery_app
from titan_workers.db import get_sync_db_session

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Batch Query Task
# ---------------------------------------------------------------------------


@celery_app.task(
    name="titan_workers.tasks.batch_tasks.run_batch_queries",
    bind=True,
    max_retries=0,  # batch jobs don't retry at task level — failures tracked per item
    queue="p1_default",
    soft_time_limit=300,  # 5 minutes for up to 50 queries
    time_limit=360,
)
def run_batch_queries(
    self: Any,
    job_id: str,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    queries: list[dict[str, Any]],
    webhook_url: str | None,
) -> dict[str, Any]:
    """Process a batch of RAG queries and store results in BatchJob.results."""
    from titan_backend.db.models.billing import BatchJob, BatchJobStatus
    from titan_backend.services.chat.service import ChatServiceSync

    with get_sync_db_session() as db:
        job = db.get(BatchJob, UUID(job_id))
        if not job:
            logger.error("batch_query_job_not_found", job_id=job_id)
            return {}

        job.status = BatchJobStatus.PROCESSING
        db.commit()

        results = []
        completed = 0
        failed = 0

        chat_service = ChatServiceSync(
            tenant_id=UUID(tenant_id),
            workspace_id=UUID(workspace_id),
            user_id=UUID(user_id),
        )

        for i, query_item in enumerate(queries):
            try:
                answer = chat_service.query_sync(
                    query=query_item["query"],
                    session_id=query_item.get("session_id"),
                    settings_override=query_item.get("rag_settings_override"),
                )
                results.append(
                    {
                        "index": i,
                        "query": query_item["query"],
                        "status": "completed",
                        "answer": answer.get("answer"),
                        "citations": answer.get("citations", []),
                        "session_id": answer.get("session_id"),
                    }
                )
                completed += 1
            except Exception as exc:
                logger.warning(
                    "batch_query_item_failed",
                    index=i,
                    query=query_item.get("query", "")[:100],
                    error=str(exc),
                )
                results.append(
                    {
                        "index": i,
                        "query": query_item["query"],
                        "status": "failed",
                        "error": str(exc),
                    }
                )
                failed += 1

            # Progress update every 5 items
            if (i + 1) % 5 == 0:
                db.execute(
                    update(BatchJob)
                    .where(BatchJob.id == UUID(job_id))
                    .values(completed_items=completed, failed_items=failed)
                )
                db.commit()

        # Final update
        final_status = (
            BatchJobStatus.COMPLETED
            if failed == 0
            else (BatchJobStatus.PARTIALLY_COMPLETED if completed > 0 else BatchJobStatus.FAILED)
        )
        db.execute(
            update(BatchJob)
            .where(BatchJob.id == UUID(job_id))
            .values(
                status=final_status,
                completed_items=completed,
                failed_items=failed,
                results={
                    "items": results,
                    "summary": {
                        "total": len(queries),
                        "completed": completed,
                        "failed": failed,
                    },
                },
                completed_at=datetime.now(UTC),
            )
        )
        db.commit()

        logger.info(
            "batch_queries_completed",
            job_id=job_id,
            total=len(queries),
            completed=completed,
            failed=failed,
        )

    if webhook_url:
        deliver_batch_webhook.apply_async(
            args=[job_id, webhook_url],
            queue="p1_default",
            countdown=2,
        )

    return {"job_id": job_id, "completed": completed, "failed": failed}


# ---------------------------------------------------------------------------
# Batch Upload Task
# ---------------------------------------------------------------------------


@celery_app.task(
    name="titan_workers.tasks.batch_tasks.run_batch_uploads",
    bind=True,
    max_retries=0,
    queue="p2_bulk_sync",
    soft_time_limit=1800,  # 30 minutes for 100 docs
    time_limit=2000,
)
def run_batch_uploads(
    self: Any,
    job_id: str,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    documents: list[dict[str, Any]],
    webhook_url: str | None,
) -> dict[str, Any]:
    """Ingest batch of document URLs via the existing ingestion pipeline."""
    from titan_backend.db.models.billing import BatchJob, BatchJobStatus
    from titan_backend.services.ingestion.orchestrator import ingest_url_sync

    with get_sync_db_session() as db:
        job = db.get(BatchJob, UUID(job_id))
        if not job:
            return {}

        job.status = BatchJobStatus.PROCESSING
        db.commit()

        results = []
        completed = 0
        failed = 0

        for i, doc_item in enumerate(documents):
            try:
                doc_result = ingest_url_sync(
                    url=doc_item["url"],
                    tenant_id=UUID(tenant_id),
                    workspace_id=UUID(workspace_id),
                    user_id=UUID(user_id),
                    folder=doc_item.get("folder"),
                    acl_groups=doc_item.get("acl_groups", []),
                    tags=doc_item.get("tags", []),
                )
                results.append(
                    {
                        "index": i,
                        "url": doc_item["url"],
                        "status": "completed",
                        "document_id": str(doc_result.get("document_id", "")),
                        "chunk_count": doc_result.get("chunk_count", 0),
                    }
                )
                completed += 1
            except Exception as exc:
                results.append(
                    {
                        "index": i,
                        "url": doc_item["url"],
                        "status": "failed",
                        "error": str(exc),
                    }
                )
                failed += 1

            # Progress update every 10 items
            if (i + 1) % 10 == 0:
                db.execute(
                    update(BatchJob)
                    .where(BatchJob.id == UUID(job_id))
                    .values(completed_items=completed, failed_items=failed)
                )
                db.commit()

        final_status = (
            BatchJobStatus.COMPLETED
            if failed == 0
            else BatchJobStatus.PARTIALLY_COMPLETED
            if completed > 0
            else BatchJobStatus.FAILED
        )
        db.execute(
            update(BatchJob)
            .where(BatchJob.id == UUID(job_id))
            .values(
                status=final_status,
                completed_items=completed,
                failed_items=failed,
                results={
                    "items": results,
                    "summary": {"total": len(documents), "completed": completed, "failed": failed},
                },
                completed_at=datetime.now(UTC),
            )
        )
        db.commit()

    if webhook_url:
        deliver_batch_webhook.apply_async(args=[job_id, webhook_url], countdown=2)

    return {"job_id": job_id, "completed": completed, "failed": failed}


# ---------------------------------------------------------------------------
# Batch Delete Task
# ---------------------------------------------------------------------------


@celery_app.task(
    name="titan_workers.tasks.batch_tasks.run_batch_deletes",
    bind=True,
    max_retries=0,
    queue="p1_default",
    soft_time_limit=600,
    time_limit=700,
)
def run_batch_deletes(
    self: Any,
    job_id: str,
    tenant_id: str,
    workspace_id: str,
    document_ids: list[str],
    webhook_url: str | None,
) -> dict[str, Any]:
    """Cascade-delete documents from Postgres, Qdrant, and MinIO."""
    from titan_backend.db.models.billing import BatchJob, BatchJobStatus
    from titan_backend.services.ingestion.deletion import delete_document_cascade_sync

    with get_sync_db_session() as db:
        job = db.get(BatchJob, UUID(job_id))
        if not job:
            return {}

        job.status = BatchJobStatus.PROCESSING
        db.commit()

        completed = 0
        failed = 0
        errors: list[dict[str, str]] = []

        for doc_id in document_ids:
            try:
                delete_document_cascade_sync(
                    document_id=UUID(doc_id),
                    tenant_id=UUID(tenant_id),
                    workspace_id=UUID(workspace_id),
                    db=db,
                )
                completed += 1
            except Exception as exc:
                failed += 1
                errors.append({"document_id": doc_id, "error": str(exc)})

        final_status = (
            BatchJobStatus.COMPLETED
            if failed == 0
            else BatchJobStatus.PARTIALLY_COMPLETED
            if completed > 0
            else BatchJobStatus.FAILED
        )
        db.execute(
            update(BatchJob)
            .where(BatchJob.id == UUID(job_id))
            .values(
                status=final_status,
                completed_items=completed,
                failed_items=failed,
                results={
                    "summary": {
                        "total": len(document_ids),
                        "deleted": completed,
                        "failed": failed,
                    },
                    "errors": errors,
                },
                completed_at=datetime.now(UTC),
            )
        )
        db.commit()

    if webhook_url:
        deliver_batch_webhook.apply_async(args=[job_id, webhook_url], countdown=2)

    return {"job_id": job_id, "completed": completed, "failed": failed}


# ---------------------------------------------------------------------------
# Webhook Delivery Task (reuses WebhookSigner from Phase 7)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="titan_workers.tasks.batch_tasks.deliver_batch_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="p1_default",
)
def deliver_batch_webhook(
    self: Any,
    job_id: str,
    webhook_url: str,
) -> dict[str, Any]:
    """Deliver batch job completion webhook with HMAC-SHA256 signature.

    Retries up to 3 times on non-2xx responses (30s, 60s, 120s backoff).
    Uses the same signing convention as Phase 7 plugin webhooks for consistency.
    """
    from titan_backend.db.models.billing import BatchJob
    from titan_backend.services.plugins.signer import WebhookSigner

    with get_sync_db_session() as db:
        job = db.get(BatchJob, UUID(job_id))
        if not job:
            return {}

        payload = {
            "job_id": job_id,
            "status": job.status.value,
            "job_type": job.job_type.value,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "results": job.results,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

        timestamp = str(int(time.time()))
        import json

        payload_str = json.dumps(payload, default=str)

        # Re-use WebhookSigner from plugin system — consistent HMAC approach
        signature, _ = WebhookSigner.sign_payload(
            secret=_get_webhook_signing_secret(),
            payload_bytes=payload_str.encode("utf-8"),
            timestamp=int(timestamp),
        )

        headers = {
            "Content-Type": "application/json",
            "X-Titan-Signature": signature,
            "X-Titan-Event": "batch.completed",
            "User-Agent": "TitanRAG-BatchWebhook/1.0",
        }

        try:
            response = httpx.post(
                webhook_url,
                content=payload_str,
                headers=headers,
                timeout=15.0,
            )
            response.raise_for_status()

            db.execute(
                update(BatchJob)
                .where(BatchJob.id == UUID(job_id))
                .values(webhook_delivered=True, webhook_attempts=job.webhook_attempts + 1)
            )
            db.commit()
            logger.info(
                "batch_webhook_delivered",
                job_id=job_id,
                status_code=response.status_code,
            )
        except (httpx.HTTPError, Exception) as exc:
            db.execute(
                update(BatchJob).where(BatchJob.id == UUID(job_id)).values(webhook_attempts=job.webhook_attempts + 1)
            )
            db.commit()
            logger.warning(
                "batch_webhook_delivery_failed",
                job_id=job_id,
                error=str(exc),
                attempt=self.request.retries + 1,
            )
            raise self.retry(exc=exc, countdown=30 * (2**self.request.retries)) from exc

    return {"delivered": True}


def _get_webhook_signing_secret() -> str:
    """Load the platform-level webhook signing secret from settings."""
    from titan_backend.core.config import settings

    return getattr(settings, "WEBHOOK_SIGNING_SECRET", "default-dev-secret-replace-in-prod")


# ---------------------------------------------------------------------------
# Sandbox Cleanup Task (Celery Beat — every hour)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="titan_workers.tasks.batch_tasks.purge_sandbox_sessions",
    queue="p1_default",
)
def purge_sandbox_sessions() -> dict[str, Any]:
    """Purge expired sandbox sessions and all associated ephemeral data.

    Runs hourly via Celery Beat. Cascades:
    - PostgreSQL: delete ephemeral tenant/workspace/user/messages
    - Qdrant: filter-delete points by ephemeral_tenant_id payload field
    - MinIO: delete objects under /_sandbox/{ephemeral_tenant_id}/
    - Redis: delete session tokens and cached queries
    """
    from sqlalchemy import and_
    from titan_backend.db.models.billing import SandboxSession

    now = datetime.now(UTC)
    purged_count = 0

    with get_sync_db_session() as db:
        expired_sessions = (
            db.execute(
                select(SandboxSession).where(
                    and_(
                        SandboxSession.expires_at < now,
                        SandboxSession.is_purged == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )

        for session in expired_sessions:
            try:
                _purge_ephemeral_tenant_data(
                    db=db,
                    ephemeral_tenant_id=session.ephemeral_tenant_id,
                    ephemeral_workspace_id=session.ephemeral_workspace_id,
                )
                session.is_purged = True
                session.purged_at = now
                purged_count += 1
            except Exception as exc:
                logger.error(
                    "sandbox_session_purge_failed",
                    session_id=str(session.id),
                    error=str(exc),
                )

        db.commit()

    logger.info("sandbox_sessions_purged", count=purged_count)
    return {"purged_sessions": purged_count}


def _purge_ephemeral_tenant_data(
    db: Any,
    ephemeral_tenant_id: UUID,
    ephemeral_workspace_id: UUID,
) -> None:
    """Delete all data for an ephemeral sandbox tenant."""
    from titan_backend.db.models.workspace import Workspace

    tenant_id_str = str(ephemeral_tenant_id)

    # 1. Delete from Qdrant (filter by tenant payload)
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        from titan_backend.core.qdrant import get_qdrant_client_sync

        qdrant = get_qdrant_client_sync()
        qdrant.delete(
            collection_name="titan_chunks",
            points_selector=Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id_str))]),
        )
    except Exception as exc:
        logger.warning("sandbox_qdrant_purge_failed", tenant_id=tenant_id_str, error=str(exc))

    # 2. Delete from MinIO
    try:
        from titan_backend.core.config import settings
        from titan_backend.core.minio import get_minio_client_sync

        minio = get_minio_client_sync()
        prefix = f"_sandbox/{tenant_id_str}/"
        objects = minio.list_objects(settings.MINIO_BUCKET, prefix=prefix, recursive=True)
        for obj in objects:
            minio.remove_object(settings.MINIO_BUCKET, obj.object_name)
    except Exception as exc:
        logger.warning("sandbox_minio_purge_failed", tenant_id=tenant_id_str, error=str(exc))

    # 3. Delete from Redis (cached queries, sessions)
    try:
        from titan_backend.core.redis import get_redis_client_sync

        redis = get_redis_client_sync()
        raw_keys = redis.keys(f"*:{tenant_id_str}:*")
        if isinstance(raw_keys, list) and raw_keys:
            redis.delete(*raw_keys)
    except Exception as exc:
        logger.warning("sandbox_redis_purge_failed", tenant_id=tenant_id_str, error=str(exc))

    # 4. Cascade delete from Postgres (relies on FK ON DELETE CASCADE)
    try:
        from titan_backend.db.models.workspaces import Workspace

        workspace = db.get(Workspace, ephemeral_workspace_id)
        if workspace:
            db.delete(workspace)
    except Exception as exc:
        logger.warning("sandbox_postgres_purge_failed", tenant_id=tenant_id_str, error=str(exc))


# ---------------------------------------------------------------------------
# Monthly CU Metering Cron (Celery Beat — 1st of each month)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="titan_workers.tasks.batch_tasks.report_monthly_cu_to_stripe",
    queue="p1_default",
)
def report_monthly_cu_to_stripe() -> dict[str, Any]:
    """Report monthly CU consumption for all PRO/ENTERPRISE tenants to Stripe.

    Runs on the 1st of each month via Celery Beat.
    Idempotent: uses {tenant_id}:{YYYY-MM} as idempotency key.
    """
    from datetime import UTC, datetime

    from titan_backend.billing.stripe_service import report_cu_usage_to_stripe
    from titan_backend.db.models.billing import StripeCustomer, StripePlanSlug

    now = datetime.now(UTC)
    # Report for the PREVIOUS month
    if now.month == 1:
        report_month = f"{now.year - 1}-12"
    else:
        report_month = f"{now.year}-{now.month - 1:02d}"

    reported = 0
    with get_sync_db_session() as db:
        # Get all paid plan tenants
        customers = (
            db.execute(
                select(StripeCustomer).where(
                    StripeCustomer.plan_slug.in_([StripePlanSlug.PRO, StripePlanSlug.ENTERPRISE])
                )
            )
            .scalars()
            .all()
        )

        for customer in customers:
            try:
                # Read CU for the report month from Redis or finops_ledger
                from titan_backend.core.redis import get_redis_client_sync

                redis = get_redis_client_sync()
                cu_used_raw = redis.get(f"quota:cu:{customer.tenant_id}:{report_month}")
                cu_str = (
                    cu_used_raw.decode("utf-8")
                    if isinstance(cu_used_raw, bytes)
                    else (str(cu_used_raw) if cu_used_raw else "0")
                )
                cu_used = Decimal(cu_str)

                if cu_used <= 0:
                    continue

                idempotency_key = f"{customer.tenant_id}:{report_month}"

                # Use asyncio.run for the async function in sync Celery context
                asyncio.run(
                    report_cu_usage_to_stripe(
                        db=db,  # type: ignore[arg-type]
                        tenant_id=str(customer.tenant_id),
                        cu_amount=cu_used,
                        idempotency_key=idempotency_key,
                    )
                )
                reported += 1
            except Exception as exc:
                logger.error(
                    "monthly_cu_report_failed",
                    tenant_id=str(customer.tenant_id),
                    error=str(exc),
                )

    logger.info("monthly_cu_reporting_done", month=report_month, reported=reported)
    return {"month": report_month, "tenants_reported": reported}
