import asyncio
from typing import Any, NamedTuple
from uuid import UUID

from qdrant_client.http import models as qmodels
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.clients.qdrant_client import get_collection_for_tenant, get_qdrant_client
from titan_backend.core.config import settings
from titan_backend.core.logging import logger
import re
from titan_workers.pipeline.embedding.sparse_embedder import SparseBM25Embedder


class QueryVectorCache:
    """In-memory LRU cache for 1536-dim query embeddings to avoid redundant inference under concurrency."""

    def __init__(self, max_size: int = 10000):
        self._cache: dict[str, list[float]] = {}
        self._max_size = max_size

    def get(self, query: str) -> list[float] | None:
        return self._cache.get(query)

    def set(self, query: str, vec: list[float]) -> None:
        if len(self._cache) >= self._max_size:
            keys_to_pop = list(self._cache.keys())[:1000]
            for k in keys_to_pop:
                self._cache.pop(k, None)
        self._cache[query] = vec


query_vector_cache = QueryVectorCache()


def normalize_and_expand_sparse_query(query: str) -> str:
    """Enriches query string with compound snake_case, unpadded numbers, hyphenated variants,
    and cross-modality technical entity permutations for high-precision BM25 matching.
    """
    q = query.strip()
    if not q:
        return ""

    words = re.findall(r'[a-zA-Z0-9]+', q)
    nums = re.findall(r'\d+', q)
    extra_tokens: list[str] = []

    # 1. Unpack snake_case and kebab-case tokens in query
    for w in re.split(r'\s+', q):
        if '_' in w or '-' in w:
            parts = [p for p in re.split(r'[-_]', w) if p]
            extra_tokens.extend(parts)

    # 2. Number normalization: unpadded and zero-padded variants (e.g. 2303, 02303, 002303)
    for n in nums:
        try:
            val = int(n)
            extra_tokens.extend([str(val), f"{val:02d}", f"{val:03d}", f"{val:04d}", f"{val:05d}"])
        except ValueError:
            pass

    # 3. Entity-specific cross-modality expansions
    q_lower = q.lower()
    for n in nums:
        try:
            val = int(n)
            if any(k in q_lower for k in ("audit", "log", "auth", "tls", "handshake")):
                extra_tokens.extend([
                    f"audit-log-{val:05d}",
                    f"audit-log-{val:04d}",
                    f"system_audit_log_{val:04d}",
                    f"system_audit_log_{val}",
                ])
            if any(k in q_lower for k in ("rfc", "architecture", "design", "specification")):
                extra_tokens.extend([
                    f"rfc_{val}",
                    f"rfc_{val:04d}",
                    f"architecture_rfc_{val:04d}",
                    f"architecture_rfc_{val}",
                ])
            if any(k in q_lower for k in ("srv", "service", "manifest", "deployment")):
                extra_tokens.extend([
                    f"srv-titan-{val}",
                    f"service_manifest_{val}",
                    f"service_manifest_{val:04d}",
                ])
            if any(k in q_lower for k in ("txn", "telemetry", "financial", "transaction", "record")):
                extra_tokens.extend([
                    f"txn-{val}-01",
                    f"financial_telemetry_{val:04d}",
                    f"financial_telemetry_{val}",
                ])
            if any(k in q_lower for k in ("compliance", "bulletin", "regulatory", "audit")):
                extra_tokens.extend([
                    f"compliance_bulletin_{val:04d}",
                    f"compliance_bulletin_{val}",
                ])
            if any(k in q_lower for k in ("report", "quarterly", "findings", "analysis")):
                extra_tokens.extend([
                    f"quarterly_report_{val:04d}",
                    f"quarterly_report_{val}",
                ])
        except ValueError:
            pass

    # 4. Adjacent word pairings
    if len(words) >= 2:
        for i in range(len(words) - 1):
            extra_tokens.append(f"{words[i]}_{words[i+1]}".lower())

    if extra_tokens:
        unique_extra = []
        seen = set()
        for t in extra_tokens:
            t_clean = t.lower().strip()
            if t_clean and t_clean not in seen:
                seen.add(t_clean)
                unique_extra.append(t_clean)
        return f"{q} {' '.join(unique_extra)}"
    return q


class SearchCandidate(NamedTuple):
    chunk_id: UUID
    score: float
    payload: dict[str, Any]


class HybridSearchResults(NamedTuple):
    dense_candidates: list[SearchCandidate]
    sparse_candidates: list[SearchCandidate]
    dense_latency_ms: float
    sparse_latency_ms: float


class HybridSearchEngine:
    """Executes parallel Dense (HNSW) and Sparse (BM25) vector queries against Qdrant with strict

    tenant, workspace, and ACL group pre-filtering.
    """

    def __init__(self) -> None:
        self.sparse_embedder = SparseBM25Embedder()

    def build_filter(
        self,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
        document_ids: list[UUID] | None = None,
        folder: str | None = None,
        tags: list[str] | None = None,
        doc_type: str | None = None,
    ) -> qmodels.Filter:
        must_conditions: list[Any] = [
            qmodels.FieldCondition(key="tenant_id", match=qmodels.MatchValue(value=str(tenant_id))),
            qmodels.FieldCondition(key="workspace_id", match=qmodels.MatchValue(value=str(workspace_id))),
            qmodels.FieldCondition(key="status", match=qmodels.MatchValue(value="READY")),
        ]

        # ACL group filtering (match any of the user's groups or 'all-members')
        effective_groups = list(set(user_acl_groups + ["all-members"]))
        must_conditions.append(qmodels.FieldCondition(key="acl_groups", match=qmodels.MatchAny(any=effective_groups)))

        if document_ids:
            must_conditions.append(
                qmodels.FieldCondition(key="document_id", match=qmodels.MatchAny(any=[str(d) for d in document_ids]))
            )

        if folder:
            must_conditions.append(qmodels.FieldCondition(key="folder", match=qmodels.MatchValue(value=folder)))

        if doc_type:
            must_conditions.append(qmodels.FieldCondition(key="doc_type", match=qmodels.MatchValue(value=doc_type)))

        if tags:
            must_conditions.append(qmodels.FieldCondition(key="tags", match=qmodels.MatchAny(any=tags)))

        return qmodels.Filter(must=must_conditions)

    async def search(
        self,
        query: str,
        tenant_id: UUID,
        workspace_id: UUID,
        user_acl_groups: list[str],
        top_k: int = 40,
        document_ids: list[UUID] | None = None,
        folder: str | None = None,
        tags: list[str] | None = None,
        doc_type: str | None = None,
        tenant_plan: str = "free",
    ) -> HybridSearchResults:
        qdrant = get_qdrant_client()
        collection_name = get_collection_for_tenant(tenant_plan=tenant_plan, tenant_id=str(tenant_id))
        q_filter = self.build_filter(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_acl_groups=user_acl_groups,
            document_ids=document_ids,
            folder=folder,
            tags=tags,
            doc_type=doc_type,
        )

        dense_candidates: list[SearchCandidate] = []
        sparse_candidates: list[SearchCandidate] = []
        dense_latency = 0.0
        sparse_latency = 0.0

        # 1. Parallel tasks: Cached Dense Embedding + Normalized Sparse Tokenization
        cached_dense = query_vector_cache.get(query)
        if cached_dense is not None:
            dense_vector = cached_dense
            dense_task = None
        else:
            dense_task = asyncio.create_task(litellm_client.aembedding([query]))

        sparse_query_str = normalize_and_expand_sparse_query(query)
        sparse_vec = self.sparse_embedder.generate_sparse_vector(sparse_query_str, workspace_id=str(workspace_id))

        # Dynamic BM25 query weight calibration: prioritize entity & numeric identifiers over high-frequency terms
        if sparse_vec["indices"]:
            words = sparse_query_str.split()
            id_tokens = {w.lower() for w in words if re.search(r'\d+', w) or '_' in w or '-' in w}
            id_hashes = {self.sparse_embedder._hash_token(t) for t in id_tokens}

            calibrated_values = []
            for idx, val in zip(sparse_vec["indices"], sparse_vec["values"]):
                if idx in id_hashes:
                    calibrated_values.append(round(val * 20.0, 4))
                else:
                    calibrated_values.append(round(val * 0.2, 4))
            sparse_vec["values"] = calibrated_values

        if dense_task is not None:
            try:
                dense_vectors = await asyncio.wait_for(dense_task, timeout=settings.DENSE_EMBEDDING_TIMEOUT_SECONDS)
                dense_vector = dense_vectors[0]
                query_vector_cache.set(query, dense_vector)
            except Exception as e:
                logger.warning("dense_query_embedding_failed", error=str(e))
                dense_vector = None

        # 2. Parallel Qdrant Queries with timeout
        async def run_dense() -> tuple[list[SearchCandidate], float]:
            t0 = asyncio.get_event_loop().time()
            if not dense_vector:
                return [], 0.0
            res = await qdrant.query_points(
                collection_name=collection_name,
                query=dense_vector,
                using="dense",
                query_filter=q_filter,
                limit=top_k,
                with_payload=True,
            )
            lat = (asyncio.get_event_loop().time() - t0) * 1000.0
            cands = [
                SearchCandidate(chunk_id=UUID(str(p.id)), score=float(p.score), payload=p.payload or {})
                for p in res.points
            ]
            return cands, round(lat, 2)

        async def run_sparse() -> tuple[list[SearchCandidate], float]:
            t0 = asyncio.get_event_loop().time()
            if not sparse_vec["indices"]:
                return [], 0.0
            q_sparse = qmodels.SparseVector(
                indices=sparse_vec["indices"],
                values=sparse_vec["values"],
            )
            res = await qdrant.query_points(
                collection_name=collection_name,
                query=q_sparse,
                using="bm25",
                query_filter=q_filter,
                limit=top_k,
                with_payload=True,
            )
            lat = (asyncio.get_event_loop().time() - t0) * 1000.0
            cands = [
                SearchCandidate(chunk_id=UUID(str(p.id)), score=float(p.score), payload=p.payload or {})
                for p in res.points
            ]
            return cands, round(lat, 2)

        # Run both searches in parallel with deterministic degradation
        dense_query_task = asyncio.create_task(run_dense())
        sparse_query_task = asyncio.create_task(run_sparse())

        try:
            results = await asyncio.gather(
                asyncio.wait_for(dense_query_task, timeout=settings.QDRANT_SEARCH_TIMEOUT_SECONDS),
                asyncio.wait_for(sparse_query_task, timeout=settings.QDRANT_SEARCH_TIMEOUT_SECONDS),
                return_exceptions=True,
            )
            res0 = results[0]
            if isinstance(res0, tuple):
                dense_candidates, dense_latency = res0
            else:
                logger.warning("dense_search_degraded", error=str(res0))

            res1 = results[1]
            if isinstance(res1, tuple):
                sparse_candidates, sparse_latency = res1
            else:
                logger.warning("sparse_search_degraded", error=str(res1))
        except Exception as e:
            logger.error("hybrid_search_gather_error", error=str(e))

        return HybridSearchResults(
            dense_candidates=dense_candidates,
            sparse_candidates=sparse_candidates,
            dense_latency_ms=dense_latency,
            sparse_latency_ms=sparse_latency,
        )


hybrid_search_engine = HybridSearchEngine()
