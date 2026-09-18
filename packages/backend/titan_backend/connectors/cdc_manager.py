import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.qdrant_client import get_qdrant_client
from titan_backend.clients.s3_client import get_minio_client
from titan_backend.connectors.base import SyncResult
from titan_backend.connectors.factory import get_connector
from titan_backend.db.models.connectors import Connector, ConnectorStatus, ConnectorSyncLog, SyncStatus
from titan_backend.db.models.documents import Document, DocumentStatus, DocumentVersion

logger = structlog.get_logger("titanrag.cdc_manager")


class CdcDeltaSyncManager:
    """
    Enterprise Change Data Capture (CDC) Delta Synchronization Engine.
    Executes incremental syncs, tombstone vector purges, MinIO storage updates,
    and source ACL permission mapping to Qdrant pre-filters.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.minio_client = get_minio_client()
        self.qdrant_client = get_qdrant_client()

    async def sync_connector(self, connector_id: uuid.UUID) -> SyncResult:
        start_time = time.perf_counter()
        stmt = select(Connector).where(Connector.id == connector_id)
        result = await self.session.execute(stmt)
        connector = result.scalar_one_or_none()
        if not connector:
            return SyncResult(
                connector_id=str(connector_id),
                status="FAILED",
                errors=[f"Connector {connector_id} not found"],
            )

        if connector.status != ConnectorStatus.ACTIVE:
            return SyncResult(
                connector_id=str(connector_id),
                status="FAILED",
                errors=[f"Connector is in status {connector.status}"],
            )

        # Create running sync log
        sync_log = ConnectorSyncLog(
            connector_id=connector.id,
            status=SyncStatus.RUNNING,
            documents_synced=0,
            documents_failed=0,
            started_at=datetime.now(UTC),
            details={"initial_cursor": connector.cdc_cursor},
        )
        self.session.add(sync_log)
        await self.session.flush()

        try:
            instance = get_connector(
                connector.connector_type,
                connector.config,
                connector.auth_credentials,
            )

            changes, next_cursor = await instance.fetch_changes(connector.cdc_cursor)
            added_count = 0
            modified_count = 0
            deleted_count = 0
            errors: list[str] = []

            for change in changes:
                try:
                    if change.change_type == "DELETED":
                        await self._handle_deleted_change(connector, change.file_id)
                        deleted_count += 1
                    else:
                        is_new = await self._handle_upsert_change(connector, instance, change)
                        if is_new:
                            added_count += 1
                        else:
                            modified_count += 1
                except Exception as ex:
                    logger.error(
                        "cdc_change_processing_error",
                        file_id=change.file_id,
                        change_type=change.change_type,
                        error=str(ex),
                    )
                    errors.append(f"File {change.file_id}: {str(ex)}")

            # Update connector metadata
            connector.cdc_cursor = next_cursor
            connector.last_synced_at = datetime.now(UTC)
            connector.sync_stats = {
                "total_added": connector.sync_stats.get("total_added", 0) + added_count,
                "total_modified": connector.sync_stats.get("total_modified", 0) + modified_count,
                "total_deleted": connector.sync_stats.get("total_deleted", 0) + deleted_count,
                "last_sync_changes": len(changes),
            }
            if errors:
                connector.last_sync_error = "; ".join(errors[:5])

            # Update sync log
            sync_log.status = SyncStatus.SUCCESS if not errors else SyncStatus.FAILED
            sync_log.documents_synced = added_count + modified_count
            sync_log.documents_failed = len(errors)
            sync_log.completed_at = datetime.now(UTC)
            sync_log.error_summary = "; ".join(errors[:3]) if errors else None
            sync_log.details = {
                "added": added_count,
                "modified": modified_count,
                "deleted": deleted_count,
                "next_cursor": next_cursor,
            }

            await self.session.commit()
            duration_ms = (time.perf_counter() - start_time) * 1000

            return SyncResult(
                connector_id=str(connector.id),
                status=sync_log.status.value,
                added_count=added_count,
                modified_count=modified_count,
                deleted_count=deleted_count,
                errors=errors,
                new_cursor=next_cursor,
                duration_ms=duration_ms,
            )

        except Exception as e:
            await self.session.rollback()
            sync_log.status = SyncStatus.FAILED
            sync_log.completed_at = datetime.now(UTC)
            sync_log.error_summary = str(e)
            connector.last_sync_error = str(e)
            await self.session.commit()

            return SyncResult(
                connector_id=str(connector.id),
                status="FAILED",
                errors=[str(e)],
            )

    async def _handle_deleted_change(self, connector: Connector, external_file_id: str) -> None:
        """Tombstone cascade deletion: mark doc deleted, purge vector projections from Qdrant."""
        stmt = select(Document).where(
            Document.workspace_id == connector.workspace_id,
            Document.meta["external_id"].as_string() == str(external_file_id),
        )
        result = await self.session.execute(stmt)
        docs = result.scalars().all()
        for doc in docs:
            doc.status = DocumentStatus.DELETING
            # Purge vectors from Qdrant
            try:
                await self.qdrant_client.delete(
                    collection_name="titan_chunks",
                    points_selector=qmodels.FilterSelector(
                        filter=qmodels.Filter(
                            must=[
                                qmodels.FieldCondition(
                                    key="document_id",
                                    match=qmodels.MatchValue(value=str(doc.id)),
                                )
                            ]
                        )
                    ),
                )
                logger.info("qdrant_tombstone_purged", doc_id=str(doc.id))
            except Exception as e:
                logger.warning("qdrant_vector_purge_warning", doc_id=str(doc.id), error=str(e))

    async def _handle_upsert_change(self, connector: Connector, instance: Any, change: Any) -> bool:
        """Download remote bytes, persist in MinIO, create/update Document, and trigger ingestion."""
        import hashlib
        import io

        if not change.file:
            return False

        content, filename = await instance.download_file(change.file_id)
        if not content:
            logger.warning("empty_content_downloaded", file_id=change.file_id)
            return False

        content_hash = hashlib.sha256(content).hexdigest()

        # Check existing document
        stmt = select(Document).where(
            Document.workspace_id == connector.workspace_id,
            Document.meta["external_id"].as_string() == str(change.file_id),
        )
        res = await self.session.execute(stmt)
        existing_doc = res.scalar_one_or_none()

        doc_id = existing_doc.id if existing_doc else uuid.uuid4()
        s3_key = f"{connector.tenant_id}/{connector.workspace_id}/{doc_id}/{filename}"

        # Upload to MinIO
        self.minio_client.put_object(
            bucket_name="titanrag-documents",
            object_name=s3_key,
            data=io.BytesIO(content),
            length=len(content),
            content_type=change.file.mime_type,
        )

        # Source ACL permissions mirroring
        source_acls = change.file.acl_permissions or []
        acl_groups = ["all-members"]
        if source_acls:
            acl_groups.extend([f"source_acl:{u.lower().strip()}" for u in source_acls])

        is_new = False
        if existing_doc:
            existing_doc.title = filename
            existing_doc.file_size_bytes = len(content)
            existing_doc.status = DocumentStatus.PROCESSING
            existing_doc.storage_path = s3_key
            existing_doc.content_hash = content_hash
            meta = dict(existing_doc.meta)
            meta.update(
                {
                    "external_id": change.file_id,
                    "connector_type": connector.connector_type,
                    "source_acls": source_acls,
                    "version": change.file.version,
                }
            )
            existing_doc.meta = meta
            doc_version = DocumentVersion(
                document_id=existing_doc.id,
                version_number=len(existing_doc.versions) + 1 if existing_doc.versions else 2,
                storage_path=s3_key,
                content_hash=content_hash,
            )
            self.session.add(doc_version)
        else:
            is_new = True
            new_doc = Document(
                id=doc_id,
                tenant_id=connector.tenant_id,
                workspace_id=connector.workspace_id,
                title=filename,
                mime_type=change.file.mime_type,
                file_size_bytes=len(content),
                status=DocumentStatus.PROCESSING,
                storage_path=s3_key,
                content_hash=content_hash,
                meta={
                    "external_id": change.file_id,
                    "connector_type": connector.connector_type,
                    "source_acls": source_acls,
                    "version": change.file.version,
                },
            )
            self.session.add(new_doc)
            doc_version = DocumentVersion(
                document_id=new_doc.id,
                version_number=1,
                storage_path=s3_key,
                content_hash=content_hash,
            )
            self.session.add(doc_version)

        # Dispatch background ingestion task
        try:
            from titan_workers.tasks.pipeline import process_document_pipeline_task

            process_document_pipeline_task.delay(
                document_id=str(doc_id),
                tenant_id=str(connector.tenant_id),
                workspace_id=str(connector.workspace_id),
                s3_key=s3_key,
                acl_groups=acl_groups,
            )
        except Exception as queue_err:
            logger.warning("celery_dispatch_skipped_or_failed", error=str(queue_err))

        return is_new
