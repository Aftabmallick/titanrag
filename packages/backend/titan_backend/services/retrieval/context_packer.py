from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.chunks import Chunk
from titan_backend.services.retrieval.reranker import RerankedCandidate


class PackedSource(NamedTuple):
    source_index: int
    chunk_id: UUID
    document_id: UUID
    document_name: str
    page_number: int | None
    bbox: dict | None
    text: str
    relevance_score: float


class ContextPacker:
    """Reorders candidate chunks to counter 'Lost in the Middle' attention degradation and

    optionally resolves parent context chunks.
    """

    def reorder_lost_in_the_middle(self, candidates: list[RerankedCandidate]) -> list[RerankedCandidate]:
        """Arranges highest-relevance passages at the beginning and end of the context block.

        Example: [1st, 3rd, 5th, 4th, 2nd]
        """
        if len(candidates) <= 2:
            return candidates

        sorted_by_score = sorted(candidates, key=lambda c: c.relevance_score, reverse=True)
        reordered: list[RerankedCandidate | None] = [None] * len(sorted_by_score)

        left = 0
        right = len(sorted_by_score) - 1

        for i, cand in enumerate(sorted_by_score):
            if i % 2 == 0:
                reordered[left] = cand
                left += 1
            else:
                reordered[right] = cand
                right -= 1

        return [c for c in reordered if c is not None]

    async def pack_context(
        self,
        candidates: list[RerankedCandidate],
        db: AsyncSession | None = None,
        parent_context_enabled: bool = False,
    ) -> list[PackedSource]:
        if not candidates:
            return []

        # 1. Lost-in-the-middle reordering
        reordered = self.reorder_lost_in_the_middle(candidates)

        # 2. Fetch parent context if enabled
        parent_texts: dict[UUID, str] = {}
        if parent_context_enabled and db is not None:
            parent_ids = [c.candidate.parent_chunk_id for c in reordered if c.candidate.parent_chunk_id]
            if parent_ids:
                stmt = select(Chunk.id, Chunk.content).where(Chunk.id.in_(parent_ids))
                res = await db.execute(stmt)
                for pid, ptext in res.all():
                    parent_texts[pid] = ptext

        # 3. Assemble indexed sources
        packed_sources: list[PackedSource] = []
        for i, item in enumerate(reordered):
            source_idx = i + 1
            cand = item.candidate
            chunk_content = cand.chunk_text

            # Prepend parent context if available
            if parent_context_enabled and cand.parent_chunk_id and cand.parent_chunk_id in parent_texts:
                p_text = parent_texts[cand.parent_chunk_id]
                chunk_content = f"[Broader Section Context: {p_text}]\n\n[Excerpt: {chunk_content}]"

            packed_sources.append(
                PackedSource(
                    source_index=source_idx,
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    document_name=cand.document_name,
                    page_number=cand.page_number,
                    bbox=cand.bbox,
                    text=chunk_content,
                    relevance_score=item.relevance_score,
                )
            )

        return packed_sources


context_packer = ContextPacker()
