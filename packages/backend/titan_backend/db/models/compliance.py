import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class GDPRDeletionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConsentPurpose(str, enum.Enum):
    TRAINING = "TRAINING"
    ANALYTICS = "ANALYTICS"
    THIRD_PARTY = "THIRD_PARTY"
    NECESSARY = "NECESSARY"


class ConsentStatus(str, enum.Enum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


class RetentionTargetResource(str, enum.Enum):
    CHAT_MESSAGES = "CHAT_MESSAGES"
    SEMANTIC_CACHE = "SEMANTIC_CACHE"
    DOCUMENT_VERSIONS = "DOCUMENT_VERSIONS"
    AUDIT_LOGS = "AUDIT_LOGS"


class RetentionAction(str, enum.Enum):
    SOFT_DELETE = "SOFT_DELETE"
    HARD_DELETE = "HARD_DELETE"
    ARCHIVE_COLD = "ARCHIVE_COLD"


class GDPRDeletionRequest(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "gdpr_deletion_requests"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    status: Mapped[GDPRDeletionStatus] = mapped_column(
        Enum(GDPRDeletionStatus, name="gdprdeletionstatus", native_enum=True),
        nullable=False,
        default=GDPRDeletionStatus.PENDING,
        index=True,
    )
    targets: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {"db": True, "qdrant": True, "minio": True, "redis": True},
    )
    audit_trail: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    verification_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_gdpr_requests_tenant_status", "tenant_id", "status"),
        Index("ix_gdpr_requests_user", "tenant_id", "user_id"),
    )


class UserConsent(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "user_consents"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[ConsentPurpose] = mapped_column(
        Enum(ConsentPurpose, name="consentpurpose", native_enum=True),
        nullable=False,
        index=True,
    )
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consentstatus", native_enum=True),
        nullable=False,
        default=ConsentStatus.GRANTED,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_user_consents_tenant_user", "tenant_id", "user_id"),
        Index("ix_user_consents_lookup", "tenant_id", "user_id", "purpose", "status"),
    )


class DataRetentionPolicy(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "data_retention_policies"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_resource: Mapped[RetentionTargetResource] = mapped_column(
        Enum(RetentionTargetResource, name="retentiontargetresource", native_enum=True),
        nullable=False,
        index=True,
    )
    ttl_days: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[RetentionAction] = mapped_column(
        Enum(RetentionAction, name="retentionaction", native_enum=True),
        nullable=False,
        default=RetentionAction.HARD_DELETE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_retention_policies_tenant_ws", "tenant_id", "workspace_id"),
        Index("ix_retention_policies_resource", "tenant_id", "target_resource", "is_active"),
    )


class RetentionAuditLog(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "retention_audit_logs"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_retention_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resource_type: Mapped[RetentionTargetResource] = mapped_column(
        Enum(RetentionTargetResource, name="retentiontargetresource", native_enum=True),
        nullable=False,
    )
    records_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_purged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_reclaimed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_retention_audit_tenant_exec", "tenant_id", "executed_at"),)
