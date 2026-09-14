import httpx
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from titan_backend.core.config import settings

logger = structlog.get_logger("titanrag.qdrant")

_qdrant_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=10,
        )
    return _qdrant_client


async def check_qdrant_health() -> bool:
    try:
        # Probe Qdrant HTTP health endpoint directly with short timeout
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.QDRANT_URL}/healthz")
            return resp.status_code == 200
    except Exception as e:
        logger.warning("qdrant_health_check_failed", error=str(e))
        return False


async def init_qdrant_collection(collection_name: str = "titan_chunks", vector_size: int = 1536) -> None:
    client = get_qdrant_client()
    collections = await client.get_collections()
    existing_names = [c.name for c in collections.collections]

    if collection_name not in existing_names:
        logger.info("creating_qdrant_collection", name=collection_name, size=vector_size)
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(
                size=vector_size,
                distance=qmodels.Distance.COSINE,
                on_disk=True,
                hnsw_config=qmodels.HnswConfigDiff(
                    m=16,
                    ef_construct=128,
                    on_disk=True,
                ),
            ),
            quantization_config=qmodels.ScalarQuantization(
                scalar=qmodels.ScalarQuantizationConfig(
                    type=qmodels.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            ),
        )

        # Create payload indexes for multi-tenant isolation and fast filtering
        index_fields = [
            ("tenant_id", qmodels.PayloadSchemaType.KEYWORD),
            ("workspace_id", qmodels.PayloadSchemaType.KEYWORD),
            ("document_id", qmodels.PayloadSchemaType.KEYWORD),
            ("acl_groups", qmodels.PayloadSchemaType.KEYWORD),
            ("status", qmodels.PayloadSchemaType.KEYWORD),
            ("created_at", qmodels.PayloadSchemaType.INTEGER),
        ]
        for field_name, schema_type in index_fields:
            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
        logger.info("qdrant_collection_ready", name=collection_name)
