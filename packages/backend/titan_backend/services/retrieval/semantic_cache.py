import hashlib
import json
from typing import Any, NamedTuple
from uuid import UUID

import numpy as np
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.logging import logger


class CachedChatResponse(NamedTuple):
    content: str
    citations: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    tokens_used: int
    similarity: float = 1.0


class SaltedSemanticCache:
    """Redis-backed ACL-salted semantic cache preventing cross-tenant and privilege-escalation data
    leaks with true vector cosine similarity matching.
    """

    def _get_sorted_groups_str(self, user_acl_groups: list[str]) -> str:
        unique_groups = sorted(set(user_acl_groups + ["all-members"]))
        # Group compaction: hash when group list is large to prevent bloated Redis keys
        if len(unique_groups) > 16:
            group_str = ",".join(unique_groups)
            return f"hash_{hashlib.sha256(group_str.encode()).hexdigest()[:16]}"
        return ",".join(unique_groups)

    def compute_partition_prefix(
        self,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
    ) -> str:
        sorted_groups = self._get_sorted_groups_str(user_acl_groups)
        return f"{tenant_id}:{workspace_id}:{sorted_groups}"

    def compute_exact_key(
        self,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
        query: str,
    ) -> str:
        prefix = self.compute_partition_prefix(tenant_id, workspace_id, user_acl_groups)
        normalized_q = query.strip().lower()
        digest = hashlib.sha256(normalized_q.encode("utf-8")).hexdigest()
        return f"semcache:exact:{prefix}:{digest}"

    compute_cache_key = compute_exact_key

    def compute_vectors_hash_key(
        self,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
    ) -> str:
        prefix = self.compute_partition_prefix(tenant_id, workspace_id, user_acl_groups)
        return f"semcache:vectors:{prefix}"

    async def get(
        self,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
        query: str,
        threshold: float = 0.95,
    ) -> CachedChatResponse | None:
        normalized_q = query.strip()
        if not normalized_q:
            return None

        # 1. Check exact key match (sub-millisecond fast path)
        exact_key = self.compute_exact_key(tenant_id, workspace_id, user_acl_groups, normalized_q)
        try:
            redis: Any = await get_redis_client()
            cached_exact = await redis.get(exact_key)
            if cached_exact:
                logger.info("semantic_cache_exact_hit", query=normalized_q)
                data = json.loads(cached_exact)
                return CachedChatResponse(
                    content=data["content"],
                    citations=data.get("citations", []),
                    sources=data.get("sources", []),
                    tokens_used=data.get("tokens_used", 0),
                    similarity=1.0,
                )
        except Exception as e:
            logger.warning("semantic_cache_exact_read_error", error=str(e))

        # 2. Vector Cosine Similarity Check (> 0.95)
        vectors_hash_key = self.compute_vectors_hash_key(tenant_id, workspace_id, user_acl_groups)
        try:
            redis = await get_redis_client()
            all_cached_entries = await redis.hgetall(vectors_hash_key)
            if not all_cached_entries:
                return None

            # Generate query embedding
            try:
                embeddings = await litellm_client.aembedding([normalized_q])
                if not embeddings or not embeddings[0]:
                    return None
                q_vec = np.array(embeddings[0], dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm == 0:
                    return None
            except Exception as e:
                logger.warning("semantic_cache_embedding_failed", error=str(e))
                return None

            best_sim = -1.0
            best_candidate: dict[str, Any] | None = None

            for _, entry_json in all_cached_entries.items():
                entry = json.loads(entry_json)
                c_vec = np.array(entry["vector"], dtype=np.float32)
                c_norm = np.linalg.norm(c_vec)
                if c_norm == 0:
                    continue
                sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
                if sim > best_sim:
                    best_sim = sim
                    best_candidate = entry

            if best_sim >= threshold and best_candidate:
                logger.info(
                    "semantic_cache_vector_hit",
                    query=normalized_q,
                    matched_query=best_candidate.get("query"),
                    similarity=round(best_sim, 4),
                    threshold=threshold,
                )
                return CachedChatResponse(
                    content=best_candidate["content"],
                    citations=best_candidate.get("citations", []),
                    sources=best_candidate.get("sources", []),
                    tokens_used=best_candidate.get("tokens_used", 0),
                    similarity=round(best_sim, 4),
                )

            logger.debug("semantic_cache_miss", query=normalized_q, best_similarity=round(best_sim, 4))
            return None

        except Exception as e:
            logger.warning("semantic_cache_vector_search_error", error=str(e))
            return None

    async def set(
        self,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
        query: str,
        content: str,
        citations: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        tokens_used: int = 0,
        ttl_seconds: int = 86400,
        query_vector: list[float] | None = None,
    ) -> None:
        normalized_q = query.strip()
        if not normalized_q or not content:
            return

        payload_base = {
            "query": normalized_q,
            "content": content,
            "citations": citations,
            "sources": sources,
            "tokens_used": tokens_used,
        }

        try:
            redis: Any = await get_redis_client()

            # 1. Set exact key
            exact_key = self.compute_exact_key(tenant_id, workspace_id, user_acl_groups, normalized_q)
            await redis.setex(exact_key, ttl_seconds, json.dumps(payload_base))

            # 2. Generate vector if not provided
            if query_vector is None:
                try:
                    embeddings = await litellm_client.aembedding([normalized_q])
                    if embeddings and embeddings[0]:
                        query_vector = embeddings[0]
                except Exception as e:
                    logger.debug("semantic_cache_set_embedding_skipped", error=str(e))

            # 3. Store in vectors hash for semantic matching
            if query_vector is not None:
                vectors_hash_key = self.compute_vectors_hash_key(tenant_id, workspace_id, user_acl_groups)
                entry_id = hashlib.sha256(normalized_q.encode("utf-8")).hexdigest()[:16]
                vector_payload = {**payload_base, "vector": query_vector}
                await redis.hset(vectors_hash_key, entry_id, json.dumps(vector_payload))
                await redis.expire(vectors_hash_key, ttl_seconds)

            logger.debug("semantic_cache_written", query=normalized_q, has_vector=query_vector is not None)
        except Exception as e:
            logger.warning("semantic_cache_write_error", error=str(e))

    async def invalidate_workspace(self, tenant_id: UUID, workspace_id: UUID) -> int:
        """Invalidates all cached entries for a given workspace upon document re-indexing or
        permission changes.
        """
        pattern = f"semcache:*:{tenant_id}:{workspace_id}:*"
        try:
            redis: Any = await get_redis_client()
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            logger.info(
                "semantic_cache_invalidated", tenant_id=str(tenant_id), workspace_id=str(workspace_id), count=deleted
            )
            return deleted
        except Exception as e:
            logger.warning("semantic_cache_invalidation_error", error=str(e))
            return 0


semantic_cache = SaltedSemanticCache()
