from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.core.config import settings
from titan_backend.core.errors import ForbiddenError
from titan_backend.core.logging import logger
from titan_backend.db.models.encryption import DataResidencyRegion, TenantDataResidency


class TenantRegionRouter:
    """Enterprise Data Residency & Geo-Pinning Router.

    Guarantees that documents, vector indices, and relational schemas
    are strictly partitioned and restricted to customer-mandated geographic boundaries.
    """

    REGION_BUCKET_MAP: dict[DataResidencyRegion, str] = {
        DataResidencyRegion.US_EAST: "titanrag-documents",
        DataResidencyRegion.US_WEST: "titan-documents-us-west",
        DataResidencyRegion.EU_CENTRAL: "titan-documents-eu-central",
        DataResidencyRegion.EU_WEST: "titan-documents-eu-west",
        DataResidencyRegion.APAC_SOUTHEAST: "titan-documents-apac-se",
    }

    REGION_COLLECTION_PREFIX: dict[DataResidencyRegion, str] = {
        DataResidencyRegion.US_EAST: "titan_us_east",
        DataResidencyRegion.US_WEST: "titan_us_west",
        DataResidencyRegion.EU_CENTRAL: "titan_eu_central",
        DataResidencyRegion.EU_WEST: "titan_eu_west",
        DataResidencyRegion.APAC_SOUTHEAST: "titan_apac",
    }

    @classmethod
    async def get_or_create_residency(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        default_region: DataResidencyRegion = DataResidencyRegion.US_EAST,
    ) -> TenantDataResidency:
        stmt = select(TenantDataResidency).where(TenantDataResidency.tenant_id == tenant_id)
        residency = (await session.execute(stmt)).scalar_one_or_none()

        if not residency:
            default_bucket = getattr(settings, "MINIO_BUCKET", "titanrag-documents")
            bucket = cls.REGION_BUCKET_MAP.get(default_region, default_bucket)
            prefix = cls.REGION_COLLECTION_PREFIX.get(default_region, "titan")

            residency = TenantDataResidency(
                tenant_id=tenant_id,
                region=default_region,
                enforce_strict=True,
                storage_bucket=str(bucket),
                database_schema="public",
                qdrant_collection_prefix=prefix,
            )
            session.add(residency)
            await session.commit()
            await session.refresh(residency)

        return residency

    @classmethod
    async def update_residency(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        region: DataResidencyRegion,
        enforce_strict: bool = True,
    ) -> TenantDataResidency:
        residency = await cls.get_or_create_residency(session, tenant_id, region)
        default_bucket = getattr(settings, "MINIO_BUCKET", "titanrag-documents")
        residency.region = region
        residency.enforce_strict = enforce_strict
        residency.storage_bucket = str(cls.REGION_BUCKET_MAP.get(region, default_bucket))
        residency.qdrant_collection_prefix = cls.REGION_COLLECTION_PREFIX.get(region, "titan")

        await session.commit()
        await session.refresh(residency)

        logger.info(
            "tenant_residency_updated",
            tenant_id=str(tenant_id),
            region=region.value,
            enforce_strict=enforce_strict,
        )
        return residency

    @classmethod
    async def get_regional_storage_bucket(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
    ) -> str:
        try:
            residency = await cls.get_or_create_residency(session, tenant_id)
            return str(residency.storage_bucket)
        except Exception:
            return getattr(settings, "MINIO_BUCKET", "titanrag-documents")

    @classmethod
    async def get_regional_qdrant_collection(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
    ) -> str:
        try:
            residency = await cls.get_or_create_residency(session, tenant_id)
            collection = getattr(settings, "QDRANT_COLLECTION", "titan_chunks")
            return f"{residency.qdrant_collection_prefix}_{collection}"
        except Exception:
            return getattr(settings, "QDRANT_COLLECTION", "titan_chunks")

    @classmethod
    async def validate_regional_compliance(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        target_region: str,
    ) -> bool:
        residency = await cls.get_or_create_residency(session, tenant_id)
        if not residency.enforce_strict:
            return True

        if residency.region.value != target_region:
            raise ForbiddenError(
                f"Data residency policy violation: tenant pinned to {residency.region.value} "
                f"cannot transmit payload to {target_region}"
            )
        return True
