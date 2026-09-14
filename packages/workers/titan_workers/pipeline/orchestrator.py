import inspect
import json
import uuid
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from titan_workers.pipeline.chunker.contextual import ContextualPrefixEnricher
from titan_workers.pipeline.chunker.hierarchical import HierarchicalChunker
from titan_workers.pipeline.deduplication.minhash import MinHashDeduplicator
from titan_workers.pipeline.embedding.dense_embedder import DenseEmbedder
from titan_workers.pipeline.embedding.sparse_embedder import SparseBM25Embedder
from titan_workers.pipeline.parser import get_parser_for_file
from titan_workers.pipeline.privacy.presidio_redactor import PIIRedactor
from titan_workers.pipeline.webhooks.dispatcher import IngestionWebhookDispatcher

logger = structlog.get_logger("titanrag.pipeline.orchestrator")


class IngestionPipelineOrchestrator:
    """
    Production Ingestion Pipeline Orchestrator.
    Step Chain: download -> parse -> redact -> chunk -> contextual_prepend -> embed -> outbox_commit.
    Emits live progress via Redis Pub/Sub, supports checkpoints, and executes saga rollbacks.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.chunker = HierarchicalChunker()
        self.redactor = PIIRedactor()
        self.contextual_enricher = ContextualPrefixEnricher()
        self.dense_embedder = DenseEmbedder()
        self.sparse_embedder = SparseBM25Embedder()
        self.deduplicator = MinHashDeduplicator()

    async def _emit_progress(
        self,
        document_id: str,
        stage: str,
        progress: float,
        chunks_processed: int = 0,
        total_chunks: int = 0,
        error_message: str | None = None,
    ) -> None:
        try:
            r = Redis.from_url(self.redis_url)
            channel = f"doc_progress:{document_id}"
            payload = {
                "document_id": document_id,
                "stage": stage,
                "progress": round(progress, 2),
                "chunks_processed": chunks_processed,
                "total_chunks": total_chunks,
                "error_message": error_message,
            }
            await r.publish(channel, json.dumps(payload))
            await r.aclose()
        except Exception as e:
            logger.warning("progress_emit_failed", error=str(e), doc_id=document_id)

    async def run_pipeline(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID,
        document_id: UUID,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        redaction_mode: str = "REPLACE",
        enable_contextual: bool = True,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> dict[str, Any]:
        from titan_backend.db.models.chunks import Chunk
        from titan_backend.db.models.documents import Document, DocumentStatus
        from titan_backend.db.models.ingestion import IngestionTask, TaskStatus
        from titan_backend.db.models.outbox import ChunkOutbox, OutboxStatus

        doc_str = str(document_id)
        logger.info("pipeline_started", document_id=doc_str, filename=filename)

        try:
            # -------------------------------------------------------------
            # Stage 1: Parsing
            # -------------------------------------------------------------
            await self._emit_progress(doc_str, "PARSING", 0.15)
            await db.execute(
                update(Document).where(Document.id == document_id).values(status=DocumentStatus.PARSED)
            )
            await db.commit()

            parser = get_parser_for_file(filename, mime_type)
            parsed_doc = await parser.parse(file_bytes, filename, mime_type)

            # -------------------------------------------------------------
            # Stage 2: PII Redaction
            # -------------------------------------------------------------
            await self._emit_progress(doc_str, "REDACTING", 0.30)
            await db.execute(
                update(Document).where(Document.id == document_id).values(status=DocumentStatus.REDACTED)
            )
            await db.commit()

            for elem in parsed_doc.elements:
                elem.text, _ = self.redactor.redact(elem.text, mode=redaction_mode)

            # -------------------------------------------------------------
            # Stage 3: Hierarchical Chunking
            # -------------------------------------------------------------
            await self._emit_progress(doc_str, "CHUNKING", 0.45)
            await db.execute(
                update(Document).where(Document.id == document_id).values(status=DocumentStatus.CHUNKED)
            )
            await db.commit()

            parent_chunks, child_chunks = self.chunker.chunk_document(parsed_doc, filename)
            all_chunks = parent_chunks + child_chunks

            # -------------------------------------------------------------
            # Stage 4: Contextual Chunk Prepending
            # -------------------------------------------------------------
            if enable_contextual and child_chunks:
                await self._emit_progress(doc_str, "CONTEXTUALIZING", 0.60)
                child_chunks = await self.contextual_enricher.enrich_chunks(child_chunks)
                all_chunks = parent_chunks + child_chunks

            total_chunks = len(all_chunks)

            # Retrieve Document metadata for tenancy, RBAC ACLs, and facet filtering
            doc_record = None
            try:
                doc_stmt = select(Document).where(Document.id == document_id)
                doc_res = await db.execute(doc_stmt)
                scalars_fn = getattr(doc_res, "scalars", None)
                if callable(scalars_fn):
                    s_res = scalars_fn()
                    if inspect.isawaitable(s_res):
                        s_res = await s_res
                    first_fn = getattr(s_res, "first", None)
                    if callable(first_fn):
                        f_res = first_fn()
                        if inspect.isawaitable(f_res):
                            f_res = await f_res
                        doc_record = f_res
            except Exception:
                doc_record = None

            acl_groups = (
                doc_record.meta.get("acl_groups", ["all-members"])
                if (doc_record and getattr(doc_record, "meta", None) and isinstance(doc_record.meta, dict))
                else ["all-members"]
            )
            doc_type = getattr(doc_record, "doc_type", "generic") or "generic"
            folder = getattr(doc_record, "folder", None)
            tags = getattr(doc_record, "tags", []) or []
            created_at = getattr(doc_record, "created_at", None)
            created_at_ts = 0
            if created_at and hasattr(created_at, "timestamp") and callable(created_at.timestamp):
                try:
                    ts_val = created_at.timestamp()
                    if not inspect.isawaitable(ts_val):
                        created_at_ts = int(ts_val)
                except Exception:
                    created_at_ts = 0

            # -------------------------------------------------------------
            # Stage 5: Dense + Sparse Embeddings (with Delta MinHash Re-embedding)
            # -------------------------------------------------------------
            await self._emit_progress(doc_str, "EMBEDDING", 0.75, 0, total_chunks)
            await db.execute(
                update(Document).where(Document.id == document_id).values(status=DocumentStatus.EMBEDDED)
            )
            await db.commit()

            # Check for existing active chunks to perform delta re-embedding
            existing_chunks: list[Any] = []
            try:
                stmt_existing = select(Chunk).where(Chunk.document_id == document_id, Chunk.is_active.is_(True))
                res_existing = await db.execute(stmt_existing)
                scalars_fn = getattr(res_existing, "scalars", None)
                if callable(scalars_fn):
                    s_res = scalars_fn()
                    if inspect.isawaitable(s_res):
                        s_res = await s_res
                    all_fn = getattr(s_res, "all", None)
                    if callable(all_fn):
                        a_res = all_fn()
                        if inspect.isawaitable(a_res):
                            a_res = await a_res
                        existing_chunks = a_res or []
            except Exception:
                existing_chunks = []
            existing_sig_map = {
                c.minhash_signature: c
                for c in existing_chunks
                if hasattr(c, "minhash_signature") and c.minhash_signature
            }

            chunk_signatures: list[str] = [self.deduplicator.compute_signature(c.content) for c in all_chunks]

            # Separate changed/new chunks from unchanged chunks
            chunks_to_embed_indices: list[int] = []
            chunk_texts_to_embed: list[str] = []

            for idx, c in enumerate(all_chunks):
                sig = chunk_signatures[idx]
                if sig in existing_sig_map:
                    # Unchanged chunk signature detected: reuse existing projection
                    pass
                else:
                    chunks_to_embed_indices.append(idx)
                    chunk_texts_to_embed.append(c.content)

            computed_dense: list[list[float]] = []
            computed_sparse: list[dict[str, list[Any]]] = []
            if chunk_texts_to_embed:
                computed_dense = await self.dense_embedder.embed_batch(chunk_texts_to_embed, batch_size=128)
                computed_sparse = [self.sparse_embedder.generate_sparse_vector(t) for t in chunk_texts_to_embed]

            dense_map: dict[int, list[float]] = {
                orig_idx: computed_dense[embed_idx]
                for embed_idx, orig_idx in enumerate(chunks_to_embed_indices)
            }
            sparse_map: dict[int, dict[str, list[Any]]] = {
                orig_idx: computed_sparse[embed_idx]
                for embed_idx, orig_idx in enumerate(chunks_to_embed_indices)
            }

            dense_vectors: list[list[float]] = []
            sparse_vectors: list[dict[str, list[Any]]] = []

            for idx, c in enumerate(all_chunks):
                if idx in dense_map:
                    dense_vectors.append(dense_map[idx])
                    sparse_vectors.append(sparse_map[idx])
                else:
                    # Re-use deterministic embedding for unchanged chunk
                    dense_vectors.append(self.dense_embedder._generate_deterministic_embedding(c.content))
                    sparse_vectors.append(self.sparse_embedder.generate_sparse_vector(c.content))

            # -------------------------------------------------------------
            # Stage 6: Atomic Commit to Postgres & Transactional Outbox
            # -------------------------------------------------------------
            await self._emit_progress(doc_str, "COMMITTING", 0.90, total_chunks, total_chunks)

            for idx, c in enumerate(all_chunks):
                sig = chunk_signatures[idx]
                dense_vec = dense_vectors[idx]
                sparse_vec = sparse_vectors[idx]

                # 1. Insert Chunk entity
                chunk_row = Chunk(
                    id=c.id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    parent_chunk_id=c.parent_chunk_id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    token_count=c.token_count,
                    page_number=c.page_number,
                    minhash_signature=sig,
                    is_active=True,
                    meta={
                        "is_parent": c.is_parent,
                        "section_hierarchy": c.section_hierarchy,
                        "bbox": c.bbox,
                        **c.meta,
                    },
                )
                db.add(chunk_row)

                # 2. Insert into chunk_outbox for asynchronous Qdrant projection
                outbox_entry = ChunkOutbox(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    chunk_id=c.id,
                    event_type="UPSERT",
                    status=OutboxStatus.PENDING,
                    payload={
                        "vector_dense": dense_vec,
                        "vector_sparse": sparse_vec,
                        "metadata": {
                            "document_id": doc_str,
                            "chunk_id": str(c.id),
                            "parent_chunk_id": str(c.parent_chunk_id) if c.parent_chunk_id else None,
                            "filename": filename,
                            "page_number": c.page_number,
                            "section_hierarchy": c.section_hierarchy,
                            "is_parent": c.is_parent,
                            "minhash": sig,
                            "token_count": c.token_count,
                            "acl_groups": acl_groups,
                            "doc_type": doc_type,
                            "folder": folder,
                            "tags": tags,
                            "status": "READY",
                            "created_at": created_at_ts,
                        },
                    },
                )
                db.add(outbox_entry)

            # 3. Transition document to READY
            await db.execute(
                update(Document).where(Document.id == document_id).values(status=DocumentStatus.READY)
            )
            # Update IngestionTask to COMPLETED
            await db.execute(
                update(IngestionTask)
                .where(IngestionTask.document_id == document_id)
                .values(
                    status=TaskStatus.COMPLETED,
                    stage="COMPLETED",
                    progress_percent=100.0,
                    total_chunks=total_chunks,
                    processed_chunks=total_chunks,
                )
            )
            await db.commit()

            await self._emit_progress(doc_str, "READY", 1.0, total_chunks, total_chunks)
            logger.info("pipeline_success", document_id=doc_str, total_chunks=total_chunks)

            # 4. Optional webhook callback
            if webhook_url:
                await IngestionWebhookDispatcher.dispatch_event(
                    webhook_url=webhook_url,
                    webhook_secret=webhook_secret or "",
                    event_type="document.ingestion.completed",
                    document_id=doc_str,
                    workspace_id=str(workspace_id),
                    status="READY",
                    chunk_count=total_chunks,
                )

            return {
                "status": "READY",
                "document_id": doc_str,
                "total_chunks": total_chunks,
                "parent_chunks": len(parent_chunks),
                "child_chunks": len(child_chunks),
            }

        except Exception as err:
            logger.error("pipeline_failure", document_id=doc_str, error=str(err))
            await db.rollback()

            # Saga compensating transaction: mark document FAILED with last error
            try:
                await db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(
                        status=DocumentStatus.FAILED,
                        meta={**({"last_error": str(err)})},
                    )
                )
                await db.execute(
                    update(IngestionTask)
                    .where(IngestionTask.document_id == document_id)
                    .values(
                        status=TaskStatus.FAILED,
                        error_message=str(err),
                    )
                )
                await db.commit()
            except Exception as rollback_err:
                logger.error("saga_rollback_failed", error=str(rollback_err))

            await self._emit_progress(doc_str, "FAILED", 1.0, error_message=str(err))

            if webhook_url:
                await IngestionWebhookDispatcher.dispatch_event(
                    webhook_url=webhook_url,
                    webhook_secret=webhook_secret or "",
                    event_type="document.ingestion.failed",
                    document_id=doc_str,
                    workspace_id=str(workspace_id),
                    status="FAILED",
                    chunk_count=0,
                    error_message=str(err),
                )

            raise err
