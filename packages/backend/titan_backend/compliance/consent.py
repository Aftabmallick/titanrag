from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.logging import logger
from titan_backend.db.models.compliance import ConsentPurpose, ConsentStatus, UserConsent


class ConsentManager:
    """Enterprise Consent Management Engine.

    Tracks explicit, purpose-bound user processing authorizations.
    Maintains fast-path caching via Redis with synchronous invalidation on status change.
    """

    @staticmethod
    def _cache_key(user_id: UUID, purpose: ConsentPurpose) -> str:
        return f"consent:{user_id}:{purpose.value}"

    @classmethod
    async def record_consent(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        purpose: ConsentPurpose,
        status: ConsentStatus = ConsentStatus.GRANTED,
        ip_address: str | None = None,
        user_agent: str | None = None,
        version: str = "v1.0",
    ) -> UserConsent:
        stmt = select(UserConsent).where(
            UserConsent.tenant_id == tenant_id,
            UserConsent.user_id == user_id,
            UserConsent.purpose == purpose,
        )
        consent = (await session.execute(stmt)).scalar_one_or_none()

        now = datetime.now(UTC)
        if consent:
            consent.status = status
            consent.ip_address = ip_address
            consent.user_agent = user_agent
            consent.version = version
            if status == ConsentStatus.REVOKED:
                consent.revoked_at = now
            else:
                consent.consented_at = now
                consent.revoked_at = None
        else:
            consent = UserConsent(
                tenant_id=tenant_id,
                user_id=user_id,
                purpose=purpose,
                status=status,
                ip_address=ip_address,
                user_agent=user_agent,
                version=version,
                consented_at=now,
                revoked_at=now if status == ConsentStatus.REVOKED else None,
            )
            session.add(consent)

        await session.commit()
        await session.refresh(consent)

        # Cache in Redis
        try:
            redis = await get_redis_client()
            await redis.set(
                cls._cache_key(user_id, purpose),
                "1" if status == ConsentStatus.GRANTED else "0",
                ex=86400,
            )
        except Exception as e:
            logger.warning("consent_cache_write_failed", error=str(e))

        logger.info("consent_recorded", user_id=str(user_id), purpose=purpose.value, status=status.value)
        return consent

    @classmethod
    async def is_consent_granted(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        purpose: ConsentPurpose,
    ) -> bool:
        # Fast path check in Redis
        try:
            redis = await get_redis_client()
            val = await redis.get(cls._cache_key(user_id, purpose))
            if val is not None:
                return bool(val == "1" or val == b"1")
        except Exception:
            pass

        # Fallback to PostgreSQL
        stmt = select(UserConsent.status).where(
            UserConsent.tenant_id == tenant_id,
            UserConsent.user_id == user_id,
            UserConsent.purpose == purpose,
        )
        status = (await session.execute(stmt)).scalar_one_or_none()
        is_granted = status == ConsentStatus.GRANTED

        try:
            redis = await get_redis_client()
            await redis.set(cls._cache_key(user_id, purpose), "1" if is_granted else "0", ex=86400)
        except Exception:
            pass

        return is_granted

    @classmethod
    async def get_user_consents(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Sequence[UserConsent]:
        stmt = (
            select(UserConsent)
            .where(
                UserConsent.tenant_id == tenant_id,
                UserConsent.user_id == user_id,
            )
            .order_by(UserConsent.created_at.desc())
        )
        return (await session.execute(stmt)).scalars().all()
