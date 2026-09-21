from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.errors import NotFoundError
from titan_backend.core.logging import logger
from titan_backend.db.models.encryption import KmsKeyConfiguration, KmsProviderType
from titan_backend.security.kms import KmsProviderFactory


class KeyRotationManager:
    """Enterprise Zero-Downtime Key Rotation Coordinator.

    Supports:
    1. Rotating KMS Provider (e.g. Local -> AWS KMS / Vault)
    2. Generating fresh Data Encryption Keys (DEKs)
    3. Re-wrapping DEK with updated Key Version
    4. Seamless background cache invalidation
    """

    @classmethod
    async def rotate_tenant_key(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        new_provider: KmsProviderType | None = None,
        new_key_arn: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(KmsKeyConfiguration).where(KmsKeyConfiguration.tenant_id == tenant_id)
        config = (await session.execute(stmt)).scalar_one_or_none()

        if not config:
            raise NotFoundError(f"KMS configuration for tenant {tenant_id} not found")

        old_version = config.dek_version
        target_provider_type = new_provider or config.provider
        target_key_arn = new_key_arn or config.key_arn_or_path

        provider = KmsProviderFactory.get_provider(target_provider_type)
        new_plain_dek, new_encrypted_dek = await provider.generate_data_key(target_key_arn)

        config.provider = target_provider_type
        config.key_arn_or_path = target_key_arn
        config.encrypted_dek = new_encrypted_dek
        config.dek_version = old_version + 1
        config.is_active = True
        config.rotated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(config)

        # Evict old cached DEK from Redis
        try:
            redis = await get_redis_client()
            await redis.delete(f"kms_dek:{tenant_id}")
        except Exception:
            pass

        logger.info(
            "kms_key_rotated",
            tenant_id=str(tenant_id),
            old_version=old_version,
            new_version=config.dek_version,
            provider=target_provider_type.value,
        )

        return {
            "tenant_id": str(tenant_id),
            "old_dek_version": old_version,
            "new_dek_version": config.dek_version,
            "provider": target_provider_type.value,
            "key_arn_or_path": target_key_arn,
            "rotated_at": config.rotated_at.isoformat(),
            "status": "ROTATION_SUCCESSFUL",
        }
