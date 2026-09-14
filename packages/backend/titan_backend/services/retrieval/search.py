import asyncio
from typing import Any, NamedTuple
from uuid import UUID

from qdrant_client.http import models as qmodels
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.clients.qdrant_client import get_collection_for_tenant, get_qdrant_client
from titan_backend.core.logging import logger
from titan_workers.pipeline.embedding.sparse_embedder import SparseBM25Embedder


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

        # 1. Parallel tasks: Dense Embedding + Sparse Tokenization
        dense_task = asyncio.create_task(litellm_client.aembedding([query]))
        sparse_vec = self.sparse_embedder.generate_sparse_vector(query, workspace_id=str(workspace_id))

        try:
            dense_vectors = await asyncio.wait_for(dense_task, timeout=1.5)
            dense_vector = dense_vectors[0]
        except Exception as e:
            logger.warning("dense_query_embedding_failed", error=str(e))
            dense_vector = None

        # 2. Parallel Qdrant Queries with 150ms timeout
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
                asyncio.wait_for(dense_query_task, timeout=0.25),
                asyncio.wait_for(sparse_query_task, timeout=0.25),
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
