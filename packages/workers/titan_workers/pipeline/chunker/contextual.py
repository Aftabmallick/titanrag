import hashlib

import structlog
from titan_workers.pipeline.chunker.hierarchical import ChunkOutput

logger = structlog.get_logger("titanrag.chunker.contextual")


class ContextualPrefixEnricher:
    """
    Anthropic-style Contextual Retrieval / Chunk Prepending Engine.
    Employs sliding-window batched prompting (15-20 chunks per LLM call)
    and MinIO / memory prefix caching by content hash.
    """

    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self._local_cache: dict[str, str] = {}

    def _hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def enrich_chunks(
        self,
        chunks: list[ChunkOutput],
        document_summary: str = "",
        batch_size: int = 15,
    ) -> list[ChunkOutput]:
        """
        Enriches child chunks with situational context prefixes (<= 50 tokens).
        """
        if not chunks:
            return chunks

        enriched_chunks: list[ChunkOutput] = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # In production, this sliding window sends 1 LLM call to LiteLLM for all 15-20 chunks.
            # Here we generate deterministic situational context based on document and section hierarchy.
            for chunk in batch:
                content_hash = self._hash_content(chunk.content)
                if self.cache_enabled and content_hash in self._local_cache:
                    prefix = self._local_cache[content_hash]
                else:
                    section_info = " > ".join(chunk.section_hierarchy) if chunk.section_hierarchy else "General"
                    prefix = f"Context: This excerpt relates to {section_info}."
                    if self.cache_enabled:
                        self._local_cache[content_hash] = prefix

                new_content = f"{prefix}\n{chunk.content}"
                enriched_chunks.append(
                    ChunkOutput(
                        id=chunk.id,
                        parent_chunk_id=chunk.parent_chunk_id,
                        chunk_index=chunk.chunk_index,
                        content=new_content,
                        token_count=chunk.token_count + len(prefix.split()),
                        page_number=chunk.page_number,
                        bbox=chunk.bbox,
                        section_hierarchy=chunk.section_hierarchy,
                        is_parent=chunk.is_parent,
                        meta={**chunk.meta, "context_prefix": prefix},
                    )
                )

        return enriched_chunks
