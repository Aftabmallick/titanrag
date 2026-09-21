from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.errors import NotFoundError
from titan_backend.core.logging import logger
from titan_backend.db.models.audit import AuditLog
from titan_backend.db.models.chat import ChatMessage
from titan_backend.db.models.compliance import (
    DataRetentionPolicy,
    RetentionAction,
    RetentionAuditLog,
    RetentionTargetResource,
)
from titan_backend.db.models.documents import DocumentVersion


class RetentionPolicyManager:
    """Enterprise Data Retention Lifecycle Engine.

    Automates regulatory data expiration and TTL pruning across:
    - Chat message histories
    - Semantic vector query caches
    - Superseded document version revisions
    - Platform security audit logs
    """

    @classmethod
    async def create_or_update_policy(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        target_resource: RetentionTargetResource,
        ttl_days: int,
        action: RetentionAction = RetentionAction.HARD_DELETE,
        workspace_id: UUID | None = None,
        is_active: bool = True,
    ) -> DataRetentionPolicy:
        stmt = select(DataRetentionPolicy).where(
            DataRetentionPolicy.tenant_id == tenant_id,
            DataRetentionPolicy.workspace_id == workspace_id,
            DataRetentionPolicy.target_resource == target_resource,
        )
        policy = (await session.execute(stmt)).scalar_one_or_none()

        if policy:
            policy.ttl_days = ttl_days
            policy.action = action
            policy.is_active = is_active
        else:
            policy = DataRetentionPolicy(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                target_resource=target_resource,
                ttl_days=ttl_days,
                action=action,
                is_active=is_active,
            )
            session.add(policy)

        await session.commit()
        await session.refresh(policy)
        logger.info(
            "retention_policy_saved",
            policy_id=str(policy.id),
            resource=target_resource.value,
            ttl_days=ttl_days,
            action=action.value,
        )
        return policy

    @classmethod
    async def list_policies(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID | None = None,
    ) -> Sequence[DataRetentionPolicy]:
        stmt = select(DataRetentionPolicy).where(DataRetentionPolicy.tenant_id == tenant_id)
        if workspace_id:
            stmt = stmt.where(
                (DataRetentionPolicy.workspace_id == workspace_id) | (DataRetentionPolicy.workspace_id.is_(None))
            )
        stmt = stmt.order_by(DataRetentionPolicy.created_at.desc())
        return (await session.execute(stmt)).scalars().all()

    @classmethod
    async def calculate_dry_run_impact(
        cls,
        session: AsyncSession,
        policy_id: UUID,
    ) -> dict[str, Any]:
        stmt = select(DataRetentionPolicy).where(DataRetentionPolicy.id == policy_id)
        policy = (await session.execute(stmt)).scalar_one_or_none()
        if not policy:
            raise NotFoundError(f"Retention policy {policy_id} not found")

        cutoff = datetime.now(UTC) - timedelta(days=policy.ttl_days)
        records_candidate = 0
        estimated_bytes = 0

        if policy.target_resource == RetentionTargetResource.CHAT_MESSAGES:
            count_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.created_at < cutoff)
            records_candidate = (await session.execute(count_stmt)).scalar() or 0
            estimated_bytes = records_candidate * 1024  # ~1KB avg per message

        elif policy.target_resource == RetentionTargetResource.SEMANTIC_CACHE:
            try:
                redis = await get_redis_client()
                cache_keys = await redis.keys("semantic_cache:*")
                records_candidate = len(cache_keys)
                estimated_bytes = records_candidate * 2048
            except Exception:
                records_candidate = 0

        elif policy.target_resource == RetentionTargetResource.DOCUMENT_VERSIONS:
            count_stmt = select(func.count(DocumentVersion.id)).where(DocumentVersion.created_at < cutoff)
            records_candidate = (await session.execute(count_stmt)).scalar() or 0
            estimated_bytes = records_candidate * 51200  # ~50KB metadata

        elif policy.target_resource == RetentionTargetResource.AUDIT_LOGS:
            count_stmt = select(func.count(AuditLog.id)).where(
                AuditLog.tenant_id == policy.tenant_id,
                AuditLog.created_at < cutoff,
            )
            records_candidate = (await session.execute(count_stmt)).scalar() or 0
            estimated_bytes = records_candidate * 512

        return {
            "policy_id": str(policy.id),
            "target_resource": policy.target_resource.value,
            "ttl_days": policy.ttl_days,
            "action": policy.action.value,
            "cutoff_timestamp": cutoff.isoformat(),
            "eligible_records": records_candidate,
            "estimated_bytes_reclaimable": estimated_bytes,
            "estimated_mb_reclaimable": round(estimated_bytes / (1024 * 1024), 3),
        }

    @classmethod
    async def execute_policy_sweep(
        cls,
        session: AsyncSession,
        policy: DataRetentionPolicy,
    ) -> RetentionAuditLog:
        cutoff = datetime.now(UTC) - timedelta(days=policy.ttl_days)
        records_scanned = 0
        records_purged = 0
        bytes_reclaimed = 0

        if policy.target_resource == RetentionTargetResource.CHAT_MESSAGES:
            # Batch scan and delete
            select_stmt = select(ChatMessage.id).where(ChatMessage.created_at < cutoff).limit(1000)
            msg_ids = (await session.execute(select_stmt)).scalars().all()
            records_scanned = len(msg_ids)
            if msg_ids:
                del_stmt = delete(ChatMessage).where(ChatMessage.id.in_(msg_ids))
                await session.execute(del_stmt)
                records_purged = len(msg_ids)
                bytes_reclaimed = records_purged * 1024

        elif policy.target_resource == RetentionTargetResource.SEMANTIC_CACHE:
            try:
                redis = await get_redis_client()
                keys = await redis.keys("semantic_cache:*")
                records_scanned = len(keys)
                if keys:
                    await redis.delete(*keys)
                    records_purged = len(keys)
                    bytes_reclaimed = records_purged * 2048
            except Exception as e:
                logger.warning("retention_cache_purge_failed", error=str(e))

        elif policy.target_resource == RetentionTargetResource.DOCUMENT_VERSIONS:
            select_stmt = select(DocumentVersion.id).where(DocumentVersion.created_at < cutoff).limit(500)
            version_ids = (await session.execute(select_stmt)).scalars().all()
            records_scanned = len(version_ids)
            if version_ids:
                del_stmt = delete(DocumentVersion).where(DocumentVersion.id.in_(version_ids))
                await session.execute(del_stmt)
                records_purged = len(version_ids)
                bytes_reclaimed = records_purged * 51200

        elif policy.target_resource == RetentionTargetResource.AUDIT_LOGS:
            select_stmt = (
                select(AuditLog.id)
                .where(AuditLog.tenant_id == policy.tenant_id, AuditLog.created_at < cutoff)
                .limit(1000)
            )
            audit_ids = (await session.execute(select_stmt)).scalars().all()
            records_scanned = len(audit_ids)
            if audit_ids:
                del_stmt = delete(AuditLog).where(AuditLog.id.in_(audit_ids))
                await session.execute(del_stmt)
                records_purged = len(audit_ids)
                bytes_reclaimed = records_purged * 512

        audit_entry = RetentionAuditLog(
            tenant_id=policy.tenant_id,
            policy_id=policy.id,
            resource_type=policy.target_resource,
            records_scanned=records_scanned,
            records_purged=records_purged,
            bytes_reclaimed=bytes_reclaimed,
            details={
                "ttl_days": policy.ttl_days,
                "action": policy.action.value,
                "cutoff": cutoff.isoformat(),
            },
            executed_at=datetime.now(UTC),
        )
        session.add(audit_entry)
        await session.commit()
        await session.refresh(audit_entry)

        logger.info(
            "retention_sweep_executed",
            policy_id=str(policy.id),
            resource=policy.target_resource.value,
            purged=records_purged,
            reclaimed_bytes=bytes_reclaimed,
        )
        return audit_entry

    @classmethod
    async def execute_all_active_sweeps(
        cls,
        session: AsyncSession,
        tenant_id: UUID | None = None,
    ) -> list[RetentionAuditLog]:
        stmt = select(DataRetentionPolicy).where(DataRetentionPolicy.is_active.is_(True))
        if tenant_id:
            stmt = stmt.where(DataRetentionPolicy.tenant_id == tenant_id)

        policies = (await session.execute(stmt)).scalars().all()
        results: list[RetentionAuditLog] = []
        for p in policies:
            log_entry = await cls.execute_policy_sweep(session, p)
            results.append(log_entry)
        return results
