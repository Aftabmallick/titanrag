import asyncio
import hashlib
import io
import json
import os
from typing import Any

import httpx
import structlog
from titan_workers.pipeline.chunker.hierarchical import ChunkOutput

logger = structlog.get_logger("titanrag.chunker.contextual")

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "titanrag-documents")


class ContextualPrefixEnricher:
    """
    Enterprise Anthropic-style Contextual Retrieval / Chunk Prepending Engine.
    Employs:
      1. Sliding-window batched prompting (15-20 chunks in 1 LLM request to LiteLLM)
      2. FinOps persistent MinIO caching: /{tenant_id}/cache/context_prefixes/{content_hash}.json
      3. Zero-crash fallback to structural hierarchy context when LLM is offline
    """

    def __init__(self, cache_enabled: bool = True, minio_client: Any | None = None):
        self.cache_enabled = cache_enabled
        self.minio_client = minio_client
        self._local_cache: dict[str, str] = {}

    def _hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _get_cached_prefix(self, tenant_id: str, content_hash: str) -> str | None:
        if not self.cache_enabled:
            return None

        # Tier 1: Local memory cache
        if content_hash in self._local_cache:
            return self._local_cache[content_hash]

        # Tier 2: MinIO persistent object cache
        if self.minio_client:
            object_name = f"{tenant_id}/cache/context_prefixes/{content_hash}.json"
            try:
                response = await asyncio.to_thread(
                    self.minio_client.get_object,
                    bucket_name=MINIO_BUCKET,
                    object_name=object_name,
                )
                data = json.loads(response.read().decode("utf-8"))
                response.close()
                response.release_conn()
                prefix: str = data.get("prefix", "")
                if prefix:
                    self._local_cache[content_hash] = prefix
                    return prefix
            except Exception:
                # Cache miss or MinIO offline
                pass

        return None

    async def _save_cached_prefix(self, tenant_id: str, content_hash: str, prefix: str) -> None:
        if not self.cache_enabled:
            return

        self._local_cache[content_hash] = prefix

        if self.minio_client:
            object_name = f"{tenant_id}/cache/context_prefixes/{content_hash}.json"
            try:
                payload = json.dumps({"prefix": prefix, "hash": content_hash}).encode("utf-8")
                await asyncio.to_thread(
                    self.minio_client.put_object,
                    bucket_name=MINIO_BUCKET,
                    object_name=object_name,
                    data=io.BytesIO(payload),
                    length=len(payload),
                    content_type="application/json",
                )
            except Exception as e:
                logger.debug("minio_prefix_cache_save_skipped", error=str(e))

    async def _fetch_llm_batched_prefixes(
        self,
        batch: list[ChunkOutput],
        document_summary: str,
    ) -> list[str]:
        """
        Sends 1 LLM request to LiteLLM generating <= 50-token situational prefixes for 15-20 chunks.
        """
        items_payload = []
        for idx, c in enumerate(batch):
            section = " > ".join(c.section_hierarchy) if c.section_hierarchy else "General"
            snippet = c.content[:300].replace("\n", " ")
            items_payload.append(f"[{idx + 1}] Section: {section} | Excerpt: {snippet}")

        prompt = (
            "You are an expert document context prepender. For each excerpt below from a larger document, "
            "provide a concise 1-sentence situational context prefix (under 30 words) explaining its context.\n"
            f"Document context: {document_summary or 'Enterprise technical document.'}\n\n"
            + "\n".join(items_payload)
            + "\n\nFormat your output strictly as:\n[1] <prefix>\n[2] <prefix>\netc."
        )

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(
                    f"{LITELLM_URL}/chat/completions",
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 500,
                    },
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"]
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    parsed_prefixes: list[str] = []
                    for line in lines:
                        if line.startswith("[") and "]" in line:
                            prefix_part = line.split("]", 1)[1].strip()
                            parsed_prefixes.append(prefix_part)
                    if len(parsed_prefixes) == len(batch):
                        return parsed_prefixes
        except Exception:
            # LiteLLM offline or timed out; fall through to deterministic fallback
            pass

        # Deterministic fallback
        return [
            f"Context: This excerpt relates to {' > '.join(c.section_hierarchy) if c.section_hierarchy else 'General Document Information'}."
            for c in batch
        ]

    async def enrich_chunks(
        self,
        chunks: list[ChunkOutput],
        document_summary: str = "",
        batch_size: int = 15,
        tenant_id: str = "default",
    ) -> list[ChunkOutput]:
        """
        Enriches child chunks with situational context prefixes (<= 50 tokens).
        """
        if not chunks:
            return chunks

        enriched_chunks: list[ChunkOutput] = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # 1. Check cache for each chunk in batch
            needed_indices: list[int] = []
            cached_prefixes: dict[int, str] = {}

            for idx, chunk in enumerate(batch):
                c_hash = self._hash_content(chunk.content)
                cached = await self._get_cached_prefix(tenant_id, c_hash)
                if cached is not None:
                    cached_prefixes[idx] = cached
                else:
                    needed_indices.append(idx)

            # 2. Batched LLM call for uncached chunks
            if needed_indices:
                needed_batch = [batch[idx] for idx in needed_indices]
                generated = await self._fetch_llm_batched_prefixes(needed_batch, document_summary)
                for gen_idx, orig_idx in enumerate(needed_indices):
                    prefix = generated[gen_idx]
                    cached_prefixes[orig_idx] = prefix
                    await self._save_cached_prefix(tenant_id, self._hash_content(batch[orig_idx].content), prefix)

            # 3. Assemble enriched chunks
            for idx, chunk in enumerate(batch):
                prefix = cached_prefixes.get(idx, "Context: General overview.")
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
