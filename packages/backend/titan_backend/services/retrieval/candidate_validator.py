from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.chunks import Chunk
from titan_backend.db.models.documents import Document, DocumentStatus


class ValidatedCandidate(NamedTuple):
    chunk_id: UUID
    document_id: UUID
    document_name: str
    parent_chunk_id: UUID | None
    section_heading: str | None
    page_number: int | None
    bbox: dict[str, Any] | None
    chunk_text: str


class CandidateValidationBarrier:
    """Zero-Trust verification barrier: Validates Qdrant-retrieved candidates against PostgreSQL.

    Eliminates phantom chunks from deleted, stale, or quarantined documents.
    """

    async def validate_candidates(
        self,
        db: AsyncSession,
        candidate_ids: list[UUID],
        tenant_id: UUID,
        workspace_id: UUID,
    ) -> dict[UUID, ValidatedCandidate]:
        if not candidate_ids:
            return {}

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.parent_chunk_id,
                Chunk.section_heading,
                Chunk.page_number,
                Chunk.bbox,
                Chunk.chunk_text,
                Document.filename,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Chunk.id.in_(candidate_ids),
                Chunk.tenant_id == tenant_id,
                Chunk.workspace_id == workspace_id,
                Chunk.status == "READY",
                Chunk.is_active.is_(True),
                Document.status == DocumentStatus.READY,
                Document.is_deleted.is_(False),
            )
        )

        result = await db.execute(stmt)
        rows = result.all()

        validated: dict[UUID, ValidatedCandidate] = {}
        for row in rows:
            c_id, doc_id, p_id, heading, page, bbox, text, filename = row
            validated[c_id] = ValidatedCandidate(
                chunk_id=c_id,
                document_id=doc_id,
                document_name=filename,
                parent_chunk_id=p_id,
                section_heading=heading,
                page_number=page,
                bbox=bbox if isinstance(bbox, dict) else None,
                chunk_text=text,
            )

        return validated


candidate_validator = CandidateValidationBarrier()
