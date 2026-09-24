"""Sandbox Demo Workspace Seeding Task — Phase 10.

Seeds pre-indexed demo documents from a canonical demo MinIO bucket
into a new ephemeral sandbox workspace without re-indexing.

Demo documents are pre-embedded and stored in a shared Qdrant collection
(read-only projection). Only Postgres metadata is created per session.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from titan_workers.celery_app import celery_app
from titan_workers.db import get_sync_db_session

logger = structlog.get_logger(__name__)

# Demo document catalog (pre-indexed, stored in shared demo collection)
DEMO_DOCUMENTS = [
    {
        "filename": "enterprise_software_architecture.pdf",
        "doc_type": "technical",
        "description": "Enterprise Software Architecture Guide — 45 pages",
        "chunk_count": 120,
        "tags": ["architecture", "enterprise", "technical"],
    },
    {
        "filename": "master_services_agreement_template.pdf",
        "doc_type": "legal",
        "description": "Master Services Agreement Template — 28 pages",
        "chunk_count": 65,
        "tags": ["legal", "contract", "MSA"],
    },
    {
        "filename": "q4_2025_financial_report.pdf",
        "doc_type": "financial",
        "description": "Q4 2025 Quarterly Financial Report — 32 pages",
        "chunk_count": 85,
        "tags": ["finance", "quarterly", "2025"],
    },
    {
        "filename": "llm_rag_research_paper.pdf",
        "doc_type": "research",
        "description": "Retrieval-Augmented Generation: A Survey — 22 pages",
        "chunk_count": 55,
        "tags": ["research", "RAG", "LLM", "AI"],
    },
    {
        "filename": "product_roadmap_2026.md",
        "doc_type": "planning",
        "description": "Product Roadmap 2026 — Markdown document",
        "chunk_count": 30,
        "tags": ["planning", "roadmap", "product"],
    },
]


@celery_app.task(
    name="titan_workers.tasks.sandbox_tasks.seed_sandbox_demo_workspace",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    queue="p2_bulk_sync",
    soft_time_limit=120,
)
def seed_sandbox_demo_workspace(
    self: Any,
    session_id: str,
    tenant_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    """Seed demo documents into a new sandbox workspace.

    Instead of full re-indexing (expensive), this task:
    1. Copies demo document records into Postgres for the ephemeral tenant
    2. Tags all pre-existing demo Qdrant points with the ephemeral tenant_id
       so the sandbox user can find them via normal ACL-scoped search
    3. Marks documents as READY immediately

    This approach means seeding is ~2 seconds instead of minutes.
    """
    from titan_backend.db.models.billing import SandboxSession

    with get_sync_db_session() as db:
        session = db.get(SandboxSession, UUID(session_id))
        if not session:
            logger.error("sandbox_session_not_found_for_seeding", session_id=session_id)
            return {}

        seeded_count = 0
        for demo_doc in DEMO_DOCUMENTS:
            try:
                doc_id = _seed_document_record(
                    db=db,
                    tenant_id=UUID(tenant_id),
                    workspace_id=UUID(workspace_id),
                    filename=str(demo_doc["filename"]),
                    doc_type=str(demo_doc["doc_type"]),
                    chunk_count=int(str(demo_doc["chunk_count"])),
                    tags=[str(t) for t in (demo_doc.get("tags") or [])],  # type: ignore[attr-defined]
                )
                _tag_demo_qdrant_points(
                    demo_filename=str(demo_doc["filename"]),
                    target_tenant_id=tenant_id,
                    target_workspace_id=workspace_id,
                    target_document_id=str(doc_id),
                )
                seeded_count += 1
            except Exception as exc:
                logger.warning(
                    "demo_doc_seeding_failed",
                    filename=demo_doc["filename"],
                    error=str(exc),
                )

        db.commit()

    logger.info(
        "sandbox_demo_workspace_seeded",
        session_id=session_id,
        seeded_documents=seeded_count,
    )
    return {"session_id": session_id, "seeded_documents": seeded_count}


def _seed_document_record(
    db: Any,
    tenant_id: UUID,
    workspace_id: UUID,
    filename: str,
    doc_type: str,
    chunk_count: int,
    tags: list[str],
) -> UUID:
    """Insert a Document record in READY state for the sandbox."""
    from uuid import uuid4

    from sqlalchemy import text

    doc_id = uuid4()
    db.execute(
        text(
            """
            INSERT INTO documents (
                id, tenant_id, workspace_id, name, original_filename,
                file_path, file_size_bytes, mime_type, status,
                chunk_count, tags, doc_type, is_demo,
                created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, :workspace_id, :name, :filename,
                :file_path, 0, 'application/pdf', 'READY',
                :chunk_count, :tags, :doc_type, true,
                now(), now()
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(doc_id),
            "tenant_id": str(tenant_id),
            "workspace_id": str(workspace_id),
            "name": filename.replace("_", " ").replace(".pdf", "").replace(".md", "").title(),
            "filename": filename,
            "file_path": f"_demo/{filename}",
            "chunk_count": chunk_count,
            "tags": tags,
            "doc_type": doc_type,
        },
    )
    return doc_id


def _tag_demo_qdrant_points(
    demo_filename: str,
    target_tenant_id: str,
    target_workspace_id: str,
    target_document_id: str,
) -> None:
    """Copy demo Qdrant points by setting payload tags for the new sandbox tenant.

    Uses Qdrant's set_payload to add the ephemeral tenant/workspace/document IDs
    to existing demo points (identified by demo_filename payload field).

    This is a zero-copy approach — we don't duplicate vectors.
    The search filter uses both the ephemeral tenant_id AND a demo_source flag.
    """
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        from titan_backend.core.qdrant import get_qdrant_client_sync

        qdrant = get_qdrant_client_sync()

        # Points tagged with demo_source=filename in the demo collection
        demo_filter = Filter(
            must=[
                FieldCondition(key="demo_source", match=MatchValue(value=demo_filename)),
                FieldCondition(key="is_demo_canonical", match=MatchValue(value=True)),
            ]
        )

        # Add sandbox tenant context to these points
        qdrant.set_payload(
            collection_name="titan_chunks",
            payload={
                f"sandbox_tenants.{target_tenant_id}": {
                    "workspace_id": target_workspace_id,
                    "document_id": target_document_id,
                }
            },
            points=demo_filter,
        )
    except Exception as exc:
        # Non-fatal — sandbox will still work, just without pre-loaded demos
        logger.warning(
            "demo_qdrant_tagging_failed",
            filename=demo_filename,
            error=str(exc),
        )
