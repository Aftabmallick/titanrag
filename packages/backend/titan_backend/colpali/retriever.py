from typing import Any
import uuid
from qdrant_client.http import models as qmodels
import structlog

from titan_backend.clients.qdrant_client import get_qdrant_client
from titan_backend.colpali.embedder import ColPaliMultiVectorEmbedder

logger = structlog.get_logger("titanrag.colpali.retriever")


class ColPaliVisualRetriever:
    """
    Retrieves visually qualified document pages using late-interaction MaxSim.
    Queries the dedicated on-disk binary quantized collection 'titan_colpali_visual'.
    """

    COLLECTION_NAME = "titan_colpali_visual"

    @classmethod
    async def search_visual_pages(
        cls,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        query: str,
        limit: int = 5,
        acl_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        client = get_qdrant_client()
        query_vectors = ColPaliMultiVectorEmbedder.embed_query(query)

        filter_conditions = [
            qmodels.FieldCondition(
                key="tenant_id",
                match=qmodels.MatchValue(value=str(tenant_id)),
            ),
            qmodels.FieldCondition(
                key="workspace_id",
                match=qmodels.MatchValue(value=str(workspace_id)),
            ),
            qmodels.FieldCondition(
                key="is_visual_qualified",
                match=qmodels.MatchValue(value=True),
            ),
        ]

        if acl_groups:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="acl_groups",
                    match=qmodels.MatchAny(any=acl_groups),
                )
            )

        qdrant_filter = qmodels.Filter(must=filter_conditions)

        try:
            # Query Qdrant multi-vector collection
            # Use average query vector for initial candidate pre-selection
            avg_q_vec = [
                sum(q[i] for q in query_vectors) / len(query_vectors)
                for i in range(len(query_vectors[0]))
            ]

            search_results = await client.search(
                collection_name=cls.COLLECTION_NAME,
                query_vector=("colpali", avg_q_vec),
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
            )

            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append({
                    "document_id": payload.get("document_id"),
                    "page_number": payload.get("page_number"),
                    "entropy_score": payload.get("entropy_score"),
                    "score": round(float(hit.score), 4),
                    "image_url": payload.get("image_url"),
                    "caption": payload.get("description", "Visual Diagram / Infographic"),
                })
            return results
        except Exception as e:
            logger.warning("colpali_search_skipped_or_failed", error=str(e))
            return []
