import asyncio
from typing import Any
import httpx
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from titan_backend.core.config import settings

logger = structlog.get_logger("titanrag.qdrant")

_qdrant_client: AsyncQdrantClient | None = None
_qdrant_loop_id: int | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global _qdrant_client, _qdrant_loop_id
    try:
        current_loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        current_loop_id = None

    if _qdrant_client is None or _qdrant_loop_id != current_loop_id:
        _qdrant_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=10,
        )
        _qdrant_loop_id = current_loop_id
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


async def init_qdrant_collection(
    collection_name: str | None = None,
    vector_size: int | None = None,
) -> None:
    client = get_qdrant_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION_NAME
    target_size = vector_size or settings.QDRANT_DENSE_VECTOR_SIZE
    try:
        collections = await client.get_collections()
        existing_names = [c.name for c in collections.collections]

        if target_collection not in existing_names:
            logger.info("creating_qdrant_collection", name=target_collection, size=target_size)
            await client.create_collection(
                collection_name=target_collection,
                vectors_config={
                    "dense": qmodels.VectorParams(
                        size=target_size,
                        distance=qmodels.Distance.COSINE,
                        on_disk=True,
                        hnsw_config=qmodels.HnswConfigDiff(
                            m=settings.QDRANT_HNSW_M,
                            ef_construct=settings.QDRANT_HNSW_EF_CONSTRUCT,
                            on_disk=True,
                        ),
                        quantization_config=qmodels.ScalarQuantization(
                            scalar=qmodels.ScalarQuantizationConfig(
                                type=qmodels.ScalarType.INT8,
                                quantile=settings.QDRANT_QUANTILE,
                                always_ram=True,
                            )
                        ),
                    )
                },
                sparse_vectors_config={
                    "bm25": qmodels.SparseVectorParams(
                        index=qmodels.SparseIndexParams(
                            on_disk=True,
                        )
                    ),
                    "splade": qmodels.SparseVectorParams(
                        index=qmodels.SparseIndexParams(
                            on_disk=True,
                        )
                    ),
                },
            )

            # Create payload indexes for multi-tenant isolation, filtering, and facets
            index_fields = [
                ("tenant_id", qmodels.PayloadSchemaType.KEYWORD),
                ("workspace_id", qmodels.PayloadSchemaType.KEYWORD),
                ("document_id", qmodels.PayloadSchemaType.KEYWORD),
                ("acl_groups", qmodels.PayloadSchemaType.KEYWORD),
                ("status", qmodels.PayloadSchemaType.KEYWORD),
                ("created_at", qmodels.PayloadSchemaType.INTEGER),
                ("doc_type", qmodels.PayloadSchemaType.KEYWORD),
                ("folder", qmodels.PayloadSchemaType.KEYWORD),
                ("tags", qmodels.PayloadSchemaType.KEYWORD),
            ]
            for field_name, schema_type in index_fields:
                await client.create_payload_index(
                    collection_name=target_collection,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            logger.info("qdrant_collection_ready", name=target_collection)
    except Exception as e:
        logger.warning("qdrant_init_collection_skipped_or_failed", error=str(e))


async def init_colpali_collection(
    collection_name: str | None = None,
    vector_size: int | None = None,
) -> None:
    """
    Dedicated physically isolated Qdrant collection for ColPali visual document pages.
    Configured with multivector MaxSim late-interaction, on-disk storage, and Binary Quantization (BQ).
    """
    client = get_qdrant_client()
    target_collection = collection_name or settings.QDRANT_COLPALI_COLLECTION_NAME
    target_size = vector_size or settings.QDRANT_COLPALI_VECTOR_SIZE
    try:
        collections = await client.get_collections()
        existing_names = [c.name for c in collections.collections]

        if target_collection not in existing_names:
            logger.info("creating_colpali_visual_collection", name=target_collection, size=target_size)
            await client.create_collection(
                collection_name=target_collection,
                vectors_config={
                    "colpali": qmodels.VectorParams(
                        size=target_size,
                        distance=qmodels.Distance.DOT,
                        multivector_config=qmodels.MultiVectorConfig(comparator=qmodels.MultiVectorComparator.MAX_SIM),
                        on_disk=True,
                        hnsw_config=qmodels.HnswConfigDiff(
                            m=settings.QDRANT_HNSW_M,
                            ef_construct=settings.QDRANT_HNSW_EF_CONSTRUCT,
                            on_disk=True,
                        ),
                        quantization_config=qmodels.BinaryQuantization(
                            binary=qmodels.BinaryQuantizationConfig(
                                always_ram=True,
                            )
                        ),
                    )
                },
            )

            # Payload indexes for tenant isolation and document page filtering
            index_fields = [
                ("tenant_id", qmodels.PayloadSchemaType.KEYWORD),
                ("workspace_id", qmodels.PayloadSchemaType.KEYWORD),
                ("document_id", qmodels.PayloadSchemaType.KEYWORD),
                ("page_number", qmodels.PayloadSchemaType.INTEGER),
                ("is_visual_qualified", qmodels.PayloadSchemaType.KEYWORD),
                ("acl_groups", qmodels.PayloadSchemaType.KEYWORD),
            ]
            for field_name, schema_type in index_fields:
                await client.create_payload_index(
                    collection_name=target_collection,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            logger.info("colpali_visual_collection_ready", name=target_collection)
    except Exception as e:
        logger.warning("colpali_collection_init_skipped_or_failed", error=str(e))


class TenantIngestionSemaphore:
    """
    Redis-backed distributed concurrency semaphore per tenant.
    Limits active concurrent ingestion / embedding jobs per tenant.
    """

    def __init__(
        self,
        tenant_id: str,
        max_concurrent: int | None = None,
        ttl_seconds: int | None = None,
    ):
        self.tenant_id = str(tenant_id)
        self.max_concurrent = max_concurrent if max_concurrent is not None else settings.QDRANT_TENANT_MAX_CONCURRENT
        self.ttl = ttl_seconds if ttl_seconds is not None else settings.QDRANT_SEMAPHORE_TTL_SECONDS
        self.key = f"semaphore:ingestion:{self.tenant_id}"
        self.acquired = False

    async def __aenter__(self) -> bool:
        from titan_backend.clients.redis_client import get_redis_client

        redis = await get_redis_client()
        current = await redis.incr(self.key)
        if current == 1:
            await redis.expire(self.key, self.ttl)

        if current > self.max_concurrent:
            await redis.decr(self.key)
            self.acquired = False
            return False

        self.acquired = True
        return True

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.acquired:
            from titan_backend.clients.redis_client import get_redis_client

            try:
                redis = await get_redis_client()
                await redis.decr(self.key)
            except Exception as e:
                logger.warning("semaphore_release_error", error=str(e), tenant_id=self.tenant_id)


def get_collection_for_tenant(tenant_plan: str = "free", tenant_id: str | None = None) -> str:
    """
    Tiered sharding routing:
    - Enterprise tenants receive dedicated Qdrant collection to prevent noisy neighbor memory thrashing
    - Free / Pro tenants use shared partitioned default collection
    """
    if tenant_plan.lower() == "enterprise" and tenant_id:
        clean_id = str(tenant_id).replace("-", "_")
        return f"titan_enterprise_{clean_id}"
    return settings.QDRANT_COLLECTION_NAME
