import asyncio
import datetime
import hashlib
import json
import uuid
import zipfile
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any
from uuid import UUID

import httpx
import structlog
from bs4 import BeautifulSoup
from fastapi import APIRouter, Body, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.documents import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentShareRequest,
    DocumentUpdateRequest,
    DocumentUploadResponse,
    DocumentVersionResponse,
    FailedDocumentItem,
    FailedDocumentsResponse,
    IngestionPreviewChunk,
    IngestionPreviewRequest,
    IngestionPreviewResponse,
    PresignedURLResponse,
    URLIngestionRequest,
)
from titan_backend.clients.qdrant_client import TenantIngestionSemaphore
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.clients.s3_client import (
    build_scoped_storage_path,
    generate_presigned_get_url,
    get_minio_client,
)
from titan_backend.core.backpressure import verify_ingestion_backpressure
from titan_backend.core.config import settings
from titan_backend.core.dependencies import CurrentUser, get_current_user, require_permission
from titan_backend.core.errors import AppException
from titan_backend.core.file_validator import scan_file_safety, validate_file_signature
from titan_backend.core.quotas import check_document_quota, check_storage_quota
from titan_backend.core.rbac import Permission
from titan_backend.db.models.chunks import Chunk
from titan_backend.db.models.documents import Document, DocumentStatus, DocumentVersion
from titan_backend.db.models.ingestion import IngestionTask, TaskStatus
from titan_backend.db.models.outbox import ChunkOutbox, OutboxStatus
from titan_backend.db.models.workspaces import Workspace
from titan_backend.db.session import get_db
from titan_backend.services.retrieval.semantic_cache import semantic_cache

logger = structlog.get_logger("titanrag.api.documents")

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["Documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    workspace_id: UUID,
    file: UploadFile = File(...),
    folder: str | None = Form(None),
    tags: str | None = Form(None),
    doc_type: str = Form("generic"),
    acl_groups: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
    _backpressure: None = Depends(verify_ingestion_backpressure),
) -> DocumentUploadResponse:
    tenant_id = current_user.tenant_id
    filename = file.filename or "upload.bin"

    # Security check: reject executable extensions
    forbidden_exts = (".exe", ".sh", ".bat", ".bin", ".cmd", ".vbs")
    if filename.lower().endswith(forbidden_exts):
        raise AppException(
            message=f"File extension not permitted for security reasons: {filename}",
            status_code=400,
            error_code="FORBIDDEN_FILE_TYPE",
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Magic byte signature and malicious payload security verification
    is_valid_sig, sig_result = validate_file_signature(file_bytes, filename)
    if not is_valid_sig:
        raise AppException(
            message=f"File validation failed: {sig_result}",
            status_code=400,
            error_code="INVALID_FILE_SIGNATURE",
        )

    is_safe, detected_threats = scan_file_safety(file_bytes, filename)
    if not is_safe:
        raise AppException(
            message=f"Malicious content pattern detected: {', '.join(detected_threats)}",
            status_code=400,
            error_code="SECURITY_THREAT_DETECTED",
        )

    # Phase 9 Streaming ClamAV Antivirus Inspection & Quarantine
    from titan_backend.db.models.encryption import QuarantineFileLog
    from titan_backend.security.scanner import ClamAVScanner

    clamav = ClamAVScanner()
    scan_res = await clamav.scan_bytes(file_bytes)
    if not scan_res.is_clean:
        q_entry = QuarantineFileLog(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            filename=filename,
            content_hash_sha256=hashlib.sha256(file_bytes).hexdigest(),
            mime_type=file.content_type or "application/octet-stream",
            file_size_bytes=file_size,
            threat_name=scan_res.threat_name or "MALWARE_DETECTED",
            quarantine_path=f"quarantine/{tenant_id}/{filename}",
            scanner_latency_ms=scan_res.latency_ms,
            details={"engine": scan_res.engine},
        )
        db.add(q_entry)
        await db.commit()
        raise AppException(
            message=f"Malicious file blocked: Threat '{scan_res.threat_name}' detected by {scan_res.engine}",
            status_code=400,
            error_code="MALWARE_DETECTED",
        )

    # 1. FinOps Quotas Check
    await check_storage_quota(tenant_id, file_size)
    await check_document_quota(tenant_id, db)

    # 2. Concurrency Semaphore Check
    sem = TenantIngestionSemaphore(tenant_id=str(tenant_id), max_concurrent=5)
    try:
        redis = await get_redis_client()
        active_str = await redis.get(sem.key)
        if active_str and int(active_str) >= sem.max_concurrent:
            raise AppException(
                message="Tenant concurrent ingestion limit reached. Please wait for ongoing jobs to complete.",
                status_code=429,
                error_code="CONCURRENCY_LIMIT_EXCEEDED",
            )
    except AppException:
        raise
    except Exception as e:
        logger.warning("concurrency_check_skipped", error=str(e))

    # 2. Content Hash & Deduplication Check
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    stmt_dup = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
        Document.content_hash == content_hash,
        Document.status != DocumentStatus.DELETING,
    )
    dup_res = await db.execute(stmt_dup)
    existing_dup = dup_res.scalars().first()

    # 3. MinIO Storage Scoping with Phase 9 Regional Geo-Pinning
    from titan_backend.compliance.residency import TenantRegionRouter

    target_bucket = await TenantRegionRouter.get_regional_storage_bucket(db, tenant_id)

    document_id = uuid.uuid4()
    storage_path = build_scoped_storage_path(tenant_id, workspace_id, document_id, filename)
    minio_client = get_minio_client()

    try:
        await asyncio.to_thread(
            minio_client.put_object,
            bucket_name=target_bucket,
            object_name=storage_path,
            data=BytesIO(file_bytes),
            length=file_size,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        if settings.ENVIRONMENT == "production" or settings.FAIL_ON_STORAGE_ERROR:
            logger.error("minio_upload_failed_production", error=str(e), path=storage_path)
            raise AppException(
                message=f"Failed to persist file in object storage: {e}",
                status_code=502,
                error_code="STORAGE_UNAVAILABLE",
            ) from e
        logger.warning("minio_upload_skipped_in_dev", error=str(e))

    # Parse metadata tags and acl_groups
    parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    parsed_acls = [a.strip() for a in acl_groups.split(",") if a.strip()] if acl_groups else ["all-members"]

    now = datetime.datetime.now(datetime.UTC)
    new_doc = Document(
        id=document_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        title=filename,
        source_type="file",
        storage_path=storage_path,
        content_hash=content_hash,
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=file_size,
        status=DocumentStatus.PENDING,
        doc_type=doc_type,
        folder=folder,
        tags=parsed_tags,
        is_stale=False,
        is_shared=False,
        created_at=now,
        updated_at=now,
        meta={"acl_groups": parsed_acls},
    )
    db.add(new_doc)

    # Initial Version
    doc_ver = DocumentVersion(
        id=uuid.uuid4(),
        document_id=document_id,
        version_number=1,
        storage_path=storage_path,
        content_hash=content_hash,
    )
    db.add(doc_ver)

    # Ingestion Task ledger
    task_id = uuid.uuid4()
    ingestion_task = IngestionTask(
        id=task_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        document_id=document_id,
        status=TaskStatus.QUEUED,
        stage="QUEUED",
        progress_percent=0.0,
    )
    db.add(ingestion_task)
    await db.commit()
    await db.refresh(new_doc)

    # 5. Dispatch async Celery task
    try:
        from titan_workers.tasks.ingestion import process_document_pipeline

        process_document_pipeline.delay(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            document_id=str(document_id),
            storage_path=storage_path,
            filename=filename,
            mime_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        if settings.ENVIRONMENT == "production" or settings.FAIL_ON_STORAGE_ERROR:
            logger.error("celery_dispatch_failed_production", error=str(e), doc_id=str(document_id))
            new_doc.status = DocumentStatus.FAILED
            ingestion_task.status = TaskStatus.FAILED
            ingestion_task.error_message = f"Task queue dispatch error: {e}"
            await db.commit()
            raise AppException(
                message="Failed to dispatch document processing task to worker queue",
                status_code=503,
                error_code="PIPELINE_UNAVAILABLE",
            ) from e
        logger.warning("celery_dispatch_skipped_in_test", error=str(e))

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(new_doc),
        task_id=task_id,
        is_duplicate=existing_dup is not None,
        duplicate_document_id=existing_dup.id if existing_dup else None,
    )


@router.post("/bulk", response_model=list[DocumentUploadResponse], status_code=201)
async def bulk_upload_documents(
    workspace_id: UUID,
    files: list[UploadFile] = File(...),
    folder: str | None = Form(None),
    tags: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> list[DocumentUploadResponse]:
    tenant_id = current_user.tenant_id
    results: list[DocumentUploadResponse] = []

    for f in files:
        filename = f.filename or "file.bin"
        file_bytes = await f.read()
        file_size = len(file_bytes)

        is_valid_sig, sig_result = validate_file_signature(file_bytes, filename)
        if not is_valid_sig:
            logger.warning("bulk_file_skipped_invalid_signature", filename=filename, reason=sig_result)
            continue
        is_safe, detected_threats = scan_file_safety(file_bytes, filename)
        if not is_safe:
            logger.warning("bulk_file_skipped_security_threat", filename=filename, threats=detected_threats)
            continue

        await check_storage_quota(tenant_id, file_size)
        await check_document_quota(tenant_id, db)

        # Handle zip archives
        if filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(BytesIO(file_bytes)) as z:
                    for zip_info in z.infolist():
                        if zip_info.is_dir() or zip_info.filename.startswith((".", "__MACOSX")):
                            continue
                        extracted_bytes = z.read(zip_info.filename)
                        extracted_filename = zip_info.filename.split("/")[-1]
                        if not extracted_filename:
                            continue

                        doc_id = uuid.uuid4()
                        c_hash = hashlib.sha256(extracted_bytes).hexdigest()
                        s_path = build_scoped_storage_path(tenant_id, workspace_id, doc_id, extracted_filename)

                        doc = Document(
                            id=doc_id,
                            tenant_id=tenant_id,
                            workspace_id=workspace_id,
                            title=extracted_filename,
                            source_type="zip",
                            storage_path=s_path,
                            content_hash=c_hash,
                            file_size_bytes=len(extracted_bytes),
                            status=DocumentStatus.PENDING,
                            folder=folder,
                            tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else [],
                            meta={},
                        )
                        db.add(doc)
                        task_id = uuid.uuid4()
                        db.add(
                            IngestionTask(
                                id=task_id,
                                tenant_id=tenant_id,
                                workspace_id=workspace_id,
                                document_id=doc_id,
                                status=TaskStatus.QUEUED,
                            )
                        )
                        await db.commit()
                        await db.refresh(doc)

                        try:
                            from titan_workers.tasks.ingestion import process_document_pipeline

                            process_document_pipeline.delay(
                                tenant_id=str(tenant_id),
                                workspace_id=str(workspace_id),
                                document_id=str(doc_id),
                                storage_path=s_path,
                                filename=extracted_filename,
                                mime_type="application/octet-stream",
                            )
                        except Exception as e:
                            logger.warning("celery_dispatch_skipped_in_test", error=str(e))

                        results.append(
                            DocumentUploadResponse(
                                document=DocumentResponse.model_validate(doc),
                                task_id=task_id,
                                is_duplicate=False,
                            )
                        )
            except Exception as e:
                logger.error("zip_extraction_failed", filename=filename, error=str(e))
        else:
            doc_id = uuid.uuid4()
            c_hash = hashlib.sha256(file_bytes).hexdigest()
            s_path = build_scoped_storage_path(tenant_id, workspace_id, doc_id, filename)
            doc = Document(
                id=doc_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                title=filename,
                source_type="file",
                storage_path=s_path,
                content_hash=c_hash,
                file_size_bytes=len(file_bytes),
                status=DocumentStatus.PENDING,
                folder=folder,
                tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else [],
                meta={},
            )
            db.add(doc)
            task_id = uuid.uuid4()
            db.add(
                IngestionTask(
                    id=task_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    document_id=doc_id,
                    status=TaskStatus.QUEUED,
                )
            )
            await db.commit()
            await db.refresh(doc)

            try:
                from titan_workers.tasks.ingestion import process_document_pipeline

                process_document_pipeline.delay(
                    tenant_id=str(tenant_id),
                    workspace_id=str(workspace_id),
                    document_id=str(doc_id),
                    storage_path=s_path,
                    filename=filename,
                    mime_type=f.content_type or "application/octet-stream",
                )
            except Exception as e:
                logger.warning("celery_dispatch_skipped_in_test", error=str(e))

            results.append(
                DocumentUploadResponse(
                    document=DocumentResponse.model_validate(doc),
                    task_id=task_id,
                    is_duplicate=False,
                )
            )

    return results


@router.post("/url", response_model=DocumentUploadResponse, status_code=201)
async def ingest_from_url(
    workspace_id: UUID,
    payload: URLIngestionRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> DocumentUploadResponse:
    tenant_id = current_user.tenant_id

    # Fetch webpage
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(payload.url)
            resp.raise_for_status()
            html_content = resp.text
    except Exception as e:
        raise AppException(
            message=f"Failed to retrieve web content from URL: {e}",
            status_code=400,
            error_code="URL_FETCH_FAILED",
        ) from e

    # Extract clean text and title
    soup = BeautifulSoup(html_content, "html.parser")
    title = payload.title or (soup.title.string.strip() if soup.title and soup.title.string else payload.url)
    # Remove script and style tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.extract()
    body_text = soup.get_text(separator="\n", strip=True)

    text_bytes = body_text.encode("utf-8")
    content_hash = hashlib.sha256(text_bytes).hexdigest()
    doc_id = uuid.uuid4()
    storage_path = build_scoped_storage_path(tenant_id, workspace_id, doc_id, f"{doc_id}.txt")

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        title=title,
        source_type="url",
        storage_path=storage_path,
        content_hash=content_hash,
        mime_type="text/plain",
        file_size_bytes=len(text_bytes),
        status=DocumentStatus.PENDING,
        doc_type="webpage",
        folder=payload.folder,
        tags=payload.tags,
        meta={"source_url": payload.url},
    )
    db.add(doc)

    task_id = uuid.uuid4()
    ingestion_task = IngestionTask(
        id=task_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        document_id=doc_id,
        status=TaskStatus.QUEUED,
    )
    db.add(ingestion_task)
    await db.commit()
    await db.refresh(doc)

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(doc),
        task_id=task_id,
        is_duplicate=False,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    workspace_id: UUID,
    folder: str | None = Query(None),
    doc_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
) -> DocumentListResponse:
    tenant_id = current_user.tenant_id
    stmt = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
        Document.status != DocumentStatus.DELETING,
    )

    if folder is not None:
        stmt = stmt.where(Document.folder == folder)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if status:
        stmt = stmt.where(Document.status == status)
    if search:
        stmt = stmt.where(Document.title.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * limit
    paged_stmt = stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(paged_stmt)
    docs = res.scalars().all()


    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total_count,
        page=page,
        limit=limit,
    )


@router.get("/failed", response_model=FailedDocumentsResponse)
async def list_failed_documents(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
) -> FailedDocumentsResponse:
    """Lists all failed ingestion documents in the workspace with root-cause error information."""
    stmt = (
        select(Document)
        .where(
            Document.tenant_id == current_user.tenant_id,
            Document.workspace_id == workspace_id,
            Document.status == DocumentStatus.FAILED,
        )
        .order_by(Document.updated_at.desc())
    )
    docs = (await db.execute(stmt)).scalars().all()

    items = []
    for d in docs:
        last_error = d.meta.get("last_error") if isinstance(d.meta, dict) else None
        items.append(
            FailedDocumentItem(
                id=d.id,
                title=d.title,
                mime_type=d.mime_type,
                file_size_bytes=d.file_size_bytes,
                status=d.status.value if hasattr(d.status, "value") else str(d.status),
                error_message=str(last_error) if last_error else None,
                created_at=d.created_at,
                updated_at=d.updated_at,
                meta=d.meta or {},
            )
        )
    return FailedDocumentsResponse(total=len(items), items=items)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
) -> DocumentResponse:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")
    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/retry", response_model=dict[str, Any])
async def retry_document_ingestion(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> dict[str, Any]:
    """Retries ingestion for a failed document by re-queuing it to the bulk ingestion pipeline."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    # Update document status to PENDING
    doc.status = DocumentStatus.PENDING
    if isinstance(doc.meta, dict):
        doc.meta["retry_triggered_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.commit()

    # Re-dispatch Celery task
    try:
        from titan_workers.tasks.ingestion import process_document_pipeline

        process_document_pipeline.delay(
            tenant_id=str(doc.tenant_id),
            workspace_id=str(doc.workspace_id),
            document_id=str(doc.id),
            storage_path=doc.storage_path,
            filename=doc.title,
            mime_type=doc.mime_type,
        )
    except Exception as e:
        logger.warning("celery_retry_dispatch_failed", error=str(e), doc_id=str(doc.id))

    return {"status": "requeued", "document_id": str(doc.id), "message": "Document ingestion re-queued successfully."}


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    workspace_id: UUID,
    document_id: UUID,
    payload: DocumentUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> DocumentResponse:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    if payload.title is not None:
        doc.title = payload.title
    if payload.folder is not None:
        doc.folder = payload.folder
    if payload.tags is not None:
        doc.tags = payload.tags
    if payload.doc_type is not None:
        doc.doc_type = payload.doc_type
    if payload.staleness_ttl_days is not None:
        doc.staleness_ttl_days = payload.staleness_ttl_days
    if payload.acl_groups is not None:
        doc.meta = {**doc.meta, "acl_groups": payload.acl_groups}
        chunk_stmt = select(Chunk).where(Chunk.document_id == document_id)
        chunks = (await db.execute(chunk_stmt)).scalars().all()
        for chunk in chunks:
            chunk.meta = {**chunk.meta, "acl_groups": payload.acl_groups}
            db.add(
                ChunkOutbox(
                    id=uuid.uuid4(),
                    tenant_id=current_user.tenant_id,
                    workspace_id=workspace_id,
                    chunk_id=chunk.id,
                    event_type="UPSERT",
                    payload={"metadata": chunk.meta},
                    status=OutboxStatus.PENDING,
                )
            )
        await semantic_cache.invalidate_workspace(current_user.tenant_id, workspace_id)

    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_documents(
    workspace_id: UUID,
    payload: BulkDeleteRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.DELETE)),
) -> BulkDeleteResponse:
    tenant_id = current_user.tenant_id
    stmt = select(Document).where(
        Document.id.in_(payload.document_ids),
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
    )
    docs = (await db.execute(stmt)).scalars().all()
    if not docs:
        return BulkDeleteResponse(deleted_count=0, document_ids=[])

    deleted_ids = [d.id for d in docs]

    for doc in docs:
        doc.status = DocumentStatus.DELETING

    chunk_stmt = select(Chunk.id).where(Chunk.document_id.in_(deleted_ids))
    chunk_ids = (await db.execute(chunk_stmt)).scalars().all()

    for cid in chunk_ids:
        db.add(
            ChunkOutbox(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                chunk_id=cid,
                event_type="DELETE",
                status=OutboxStatus.PENDING,
            )
        )

    await db.execute(delete(Chunk).where(Chunk.document_id.in_(deleted_ids)))

    minio_client = get_minio_client()
    for doc in docs:
        try:
            await asyncio.to_thread(
                minio_client.remove_object,
                bucket_name=settings.MINIO_BUCKET,
                object_name=doc.storage_path,
            )
        except Exception as e:
            logger.warning("minio_bulk_delete_warning", path=doc.storage_path, error=str(e))
        await db.delete(doc)

    await db.commit()
    await semantic_cache.invalidate_workspace(tenant_id, workspace_id)
    return BulkDeleteResponse(deleted_count=len(deleted_ids), document_ids=deleted_ids)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.DELETE)),
) -> None:
    tenant_id = current_user.tenant_id
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    # 1. Mark as DELETING tombstone
    doc.status = DocumentStatus.DELETING

    # 2. Add DELETE events into chunk_outbox for Qdrant projection deletion
    chunk_stmt = select(Chunk.id).where(Chunk.document_id == document_id)
    chunk_ids = (await db.execute(chunk_stmt)).scalars().all()

    for cid in chunk_ids:
        db.add(
            ChunkOutbox(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                chunk_id=cid,
                event_type="DELETE",
                status=OutboxStatus.PENDING,
            )
        )

    # 3. Delete chunks from Postgres
    await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

    # 4. Remove object from MinIO
    try:
        minio_client = get_minio_client()
        await asyncio.to_thread(
            minio_client.remove_object,
            bucket_name=settings.MINIO_BUCKET,
            object_name=doc.storage_path,
        )
    except Exception as e:
        logger.warning("minio_delete_warning", path=doc.storage_path, error=str(e))

    # 5. Remove document
    await db.delete(doc)
    await db.commit()
    await semantic_cache.invalidate_workspace(tenant_id, workspace_id)


@router.get("/{document_id}/download-url", response_model=PresignedURLResponse)
@router.get("/{document_id}/download", response_model=PresignedURLResponse)
async def get_document_download_url(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.DOWNLOAD)),
) -> PresignedURLResponse:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    url = await generate_presigned_get_url(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        document_id=document_id,
        filename=doc.title,
        user_role=current_user.role,
        user_id=current_user.id,
        action="download",
        db=db,
    )
    return PresignedURLResponse(url=url, expires_in=900, action="download")


@router.get("/{document_id}/view-url", response_model=PresignedURLResponse)
async def get_document_view_url(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
) -> PresignedURLResponse:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    url = await generate_presigned_get_url(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        document_id=document_id,
        filename=doc.title,
        user_role=current_user.role,
        user_id=current_user.id,
        action="view",
        db=db,
    )
    return PresignedURLResponse(url=url, expires_in=900, action="view")


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
) -> list[DocumentVersionResponse]:
    doc = (
        (
            await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.tenant_id == current_user.tenant_id,
                    Document.workspace_id == workspace_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.asc())
    )
    versions = (await db.execute(stmt)).scalars().all()
    return [DocumentVersionResponse.model_validate(v) for v in versions]


@router.post("/{document_id}/versions", response_model=DocumentUploadResponse, status_code=201)
async def create_document_version(
    workspace_id: UUID,
    document_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> DocumentUploadResponse:
    tenant_id = current_user.tenant_id
    filename = file.filename or "upload.bin"

    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    forbidden_exts = (".exe", ".sh", ".bat", ".bin", ".cmd", ".vbs")
    if filename.lower().endswith(forbidden_exts):
        raise AppException(
            message=f"File extension not permitted for security reasons: {filename}",
            status_code=400,
            error_code="FORBIDDEN_FILE_TYPE",
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    is_valid_sig, sig_result = validate_file_signature(file_bytes, filename)
    if not is_valid_sig:
        raise AppException(
            message=f"File validation failed: {sig_result}",
            status_code=400,
            error_code="INVALID_FILE_SIGNATURE",
        )

    is_safe, detected_threats = scan_file_safety(file_bytes, filename)
    if not is_safe:
        raise AppException(
            message=f"Malicious content pattern detected: {', '.join(detected_threats)}",
            status_code=400,
            error_code="SECURITY_THREAT_DETECTED",
        )

    await check_storage_quota(tenant_id, file_size)

    content_hash = hashlib.sha256(file_bytes).hexdigest()

    v_stmt = select(func.coalesce(func.max(DocumentVersion.version_number), 1)).where(
        DocumentVersion.document_id == document_id
    )
    current_max_v = (await db.execute(v_stmt)).scalar() or 1
    next_version = current_max_v + 1

    version_filename = f"v{next_version}_{filename}"
    storage_path = build_scoped_storage_path(tenant_id, workspace_id, document_id, version_filename)
    minio_client = get_minio_client()

    try:
        await asyncio.to_thread(
            minio_client.put_object,
            bucket_name=settings.MINIO_BUCKET,
            object_name=storage_path,
            data=BytesIO(file_bytes),
            length=file_size,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        logger.warning("minio_version_upload_skipped_in_dev", error=str(e))

    doc_ver = DocumentVersion(
        id=uuid.uuid4(),
        document_id=document_id,
        version_number=next_version,
        storage_path=storage_path,
        content_hash=content_hash,
    )
    db.add(doc_ver)

    chunk_stmt = select(Chunk.id).where(Chunk.document_id == document_id, Chunk.is_active.is_(True))
    old_chunk_ids = (await db.execute(chunk_stmt)).scalars().all()
    for cid in old_chunk_ids:
        db.add(
            ChunkOutbox(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                chunk_id=cid,
                event_type="DELETE",
                status=OutboxStatus.PENDING,
            )
        )
    await db.execute(update(Chunk).where(Chunk.document_id == document_id).values(is_active=False))

    doc.storage_path = storage_path
    doc.content_hash = content_hash
    doc.file_size_bytes = file_size
    doc.status = DocumentStatus.PENDING
    now = datetime.datetime.now(datetime.UTC)
    doc.updated_at = now

    task_id = uuid.uuid4()
    db.add(
        IngestionTask(
            id=task_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            document_id=document_id,
            status=TaskStatus.QUEUED,
            stage="QUEUED",
            progress_percent=0.0,
        )
    )
    await db.commit()
    await db.refresh(doc)
    await semantic_cache.invalidate_workspace(tenant_id, workspace_id)

    try:
        from titan_workers.tasks.ingestion import process_document_pipeline

        process_document_pipeline.delay(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            document_id=str(document_id),
            storage_path=storage_path,
            filename=filename,
            mime_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        logger.warning("celery_dispatch_skipped_in_test", error=str(e))

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(doc),
        task_id=task_id,
        is_duplicate=False,
    )


@router.post("/{document_id}/share", response_model=DocumentResponse)
async def share_document(
    workspace_id: UUID,
    document_id: UUID,
    payload: DocumentShareRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> DocumentResponse:
    tenant_id = current_user.tenant_id
    # Ensure source doc exists
    doc = (
        (
            await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.tenant_id == tenant_id,
                    Document.workspace_id == workspace_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not doc:
        raise AppException(message="Source document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    # Ensure target workspace exists and belongs to SAME tenant (cross-tenant hard block)
    target_ws = (
        (
            await db.execute(
                select(Workspace).where(
                    Workspace.id == payload.target_workspace_id,
                    Workspace.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not target_ws:
        raise AppException(
            message="Target workspace not found or cross-tenant share attempted.",
            status_code=403,
            error_code="CROSS_TENANT_SHARE_FORBIDDEN",
        )

    # Create read-only shared reference
    shared_doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        workspace_id=payload.target_workspace_id,
        title=doc.title,
        source_type="shared",
        storage_path=doc.storage_path,
        content_hash=doc.content_hash,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        doc_type=doc.doc_type,
        folder="Shared",
        tags=["shared"],
        is_shared=True,
        shared_from_workspace_id=workspace_id,
        meta={"original_document_id": str(doc.id)},
    )
    db.add(shared_doc)
    await db.commit()
    await db.refresh(shared_doc)
    return DocumentResponse.model_validate(shared_doc)


@router.post("/preview", response_model=IngestionPreviewResponse)
async def preview_ingestion(
    request: Request,
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.UPLOAD)),
) -> IngestionPreviewResponse:
    """
    Ingestion preview endpoint: parses and chunks content without writing to Qdrant or DB.
    Supports both multipart form-data (file upload from UI) and JSON body (programmatic API).
    """
    from titan_workers.pipeline.chunker.hierarchical import HierarchicalChunker
    from titan_workers.pipeline.parser import get_parser_for_file

    content_type = request.headers.get("content-type", "")
    filename = "preview.txt"
    mime_type = "text/plain"
    content_bytes = b""

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            content_bytes = await uploaded_file.read()
            filename = getattr(uploaded_file, "filename", "preview.txt") or "preview.txt"
            mime_type = getattr(uploaded_file, "content_type", "text/plain") or "text/plain"
        elif isinstance(uploaded_file, (str, bytes)):
            content_bytes = uploaded_file.encode("utf-8") if isinstance(uploaded_file, str) else uploaded_file
            filename = str(form.get("filename") or "preview.txt")
    else:
        try:
            body_data = await request.json()
            payload = IngestionPreviewRequest(**body_data)
            content_bytes = (payload.file_content or "Sample document text for preview.").encode("utf-8")
            filename = payload.filename
            mime_type = payload.mime_type
        except Exception:
            content_bytes = b"Sample document text for preview."

    if not content_bytes:
        content_bytes = b"Sample document text for preview."

    parser = get_parser_for_file(filename, mime_type)
    parsed_doc = await parser.parse(content_bytes, filename, mime_type)

    chunker = HierarchicalChunker()
    parents, children = chunker.chunk_document(parsed_doc, filename)

    sample_items: list[IngestionPreviewChunk] = []
    for c in parents[:2] + children[:3]:
        sample_items.append(
            IngestionPreviewChunk(
                index=c.chunk_index,
                content=c.content[:200] + ("..." if len(c.content) > 200 else ""),
                token_count=c.token_count,
                is_parent=c.is_parent,
                chunk_type="PARENT" if c.is_parent else "CHILD",
                section_heading=c.meta.get("section_heading") or c.meta.get("heading"),
                context_prefix=c.meta.get("context_prefix"),
                meta=c.meta,
            )
        )

    return IngestionPreviewResponse(
        filename=filename,
        total_chunks=len(parents) + len(children),
        parent_chunks=len(parents),
        child_chunks=len(children),
        total_parent_chunks=len(parents),
        total_child_chunks=len(children),
        sample_chunks=sample_items,
    )


@router.post("/{document_id}/reindex", response_model=DocumentUploadResponse)
async def reindex_document(
    workspace_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.REINDEX)),
) -> DocumentUploadResponse:
    """
    Re-indexes an individual document:
    1. Stages outbox DELETE events to purge old vector projections in Qdrant.
    2. Marks existing chunks inactive in Postgres.
    3. Resets document status to PENDING and queues new IngestionTask.
    4. Dispatches asynchronous Celery pipeline worker.
    """
    tenant_id = current_user.tenant_id
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc:
        raise AppException(message="Document not found.", status_code=404, error_code="DOCUMENT_NOT_FOUND")

    # 1. Fetch existing chunks and stage DELETE outbox events
    chunk_stmt = select(Chunk.id).where(Chunk.document_id == document_id)
    chunk_ids = (await db.execute(chunk_stmt)).scalars().all()
    for cid in chunk_ids:
        db.add(
            ChunkOutbox(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                chunk_id=cid,
                event_type="DELETE",
                status=OutboxStatus.PENDING,
            )
        )

    # 2. Mark existing chunks inactive in Postgres
    await db.execute(update(Chunk).where(Chunk.document_id == document_id).values(is_active=False))

    # 3. Reset document status to PENDING
    doc.status = DocumentStatus.PENDING
    task_id = uuid.uuid4()
    ingestion_task = IngestionTask(
        id=task_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        document_id=document_id,
        status=TaskStatus.QUEUED,
        stage="QUEUED",
        progress_percent=0.0,
    )
    db.add(ingestion_task)
    await db.commit()
    await db.refresh(doc)

    # 4. Dispatch Celery task
    try:
        from titan_workers.tasks.ingestion import process_document_pipeline

        process_document_pipeline.delay(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            document_id=str(document_id),
            storage_path=doc.storage_path,
            filename=doc.title,
            mime_type=doc.mime_type,
        )
    except Exception as e:
        logger.warning("celery_dispatch_skipped_in_test", error=str(e))

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(doc),
        task_id=task_id,
        is_duplicate=False,
    )


@router.post("/reindex", response_model=list[DocumentUploadResponse])
async def bulk_reindex_documents(
    workspace_id: UUID,
    folder: str | None = Query(None),
    doc_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.REINDEX)),
) -> list[DocumentUploadResponse]:
    """
    Bulk re-indexes all active documents in a workspace or within a folder.
    """
    tenant_id = current_user.tenant_id
    stmt = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.workspace_id == workspace_id,
        Document.status != DocumentStatus.DELETING,
    )
    if folder:
        stmt = stmt.where(Document.folder == folder)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)

    docs = (await db.execute(stmt)).scalars().all()
    results: list[DocumentUploadResponse] = []

    for doc in docs:
        chunk_stmt = select(Chunk.id).where(Chunk.document_id == doc.id)
        chunk_ids = (await db.execute(chunk_stmt)).scalars().all()
        for cid in chunk_ids:
            db.add(
                ChunkOutbox(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    chunk_id=cid,
                    event_type="DELETE",
                    status=OutboxStatus.PENDING,
                )
            )
        await db.execute(update(Chunk).where(Chunk.document_id == doc.id).values(is_active=False))
        doc.status = DocumentStatus.PENDING
        task_id = uuid.uuid4()
        db.add(
            IngestionTask(
                id=task_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                document_id=doc.id,
                status=TaskStatus.QUEUED,
                stage="QUEUED",
            )
        )
        await db.commit()
        await db.refresh(doc)

        try:
            from titan_workers.tasks.ingestion import process_document_pipeline

            process_document_pipeline.delay(
                tenant_id=str(tenant_id),
                workspace_id=str(workspace_id),
                document_id=str(doc.id),
                storage_path=doc.storage_path,
                filename=doc.title,
                mime_type=doc.mime_type,
            )
        except Exception as e:
            logger.warning("celery_dispatch_skipped_in_test", error=str(e))

        results.append(
            DocumentUploadResponse(
                document=DocumentResponse.model_validate(doc),
                task_id=task_id,
                is_duplicate=False,
            )
        )

    return results


@router.get("/{document_id}/status")
async def stream_document_status(
    workspace_id: UUID,
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """
    Real-time Server-Sent Events (SSE) progress endpoint listening to Redis Pub/Sub channel.
    """
    doc_str = str(document_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            r = Redis.from_url(settings.REDIS_URL)
            pubsub = r.pubsub()
            channel = f"doc_progress:{doc_str}"
            await pubsub.subscribe(channel)

            # Yield initial connect event
            yield f"data: {json.dumps({'stage': 'CONNECTED', 'progress': 0.0, 'document_id': doc_str})}\n\n"

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data_str = (
                        message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                    )
                    yield f"data: {data_str}\n\n"
                    payload = json.loads(data_str)
                    if payload.get("stage") in ("READY", "FAILED"):
                        break
                await asyncio.sleep(0.5)

            await pubsub.unsubscribe(channel)
            await r.aclose()
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'ERROR', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
