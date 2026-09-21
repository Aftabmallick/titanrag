import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class KmsProviderType(str, enum.Enum):
    LOCAL = "LOCAL"
    AWS_KMS = "AWS_KMS"
    GCP_KMS = "GCP_KMS"
    HASHICORP_VAULT = "HASHICORP_VAULT"


class DataResidencyRegion(str, enum.Enum):
    US_EAST = "US_EAST"
    US_WEST = "US_WEST"
    EU_CENTRAL = "EU_CENTRAL"
    EU_WEST = "EU_WEST"
    APAC_SOUTHEAST = "APAC_SOUTHEAST"


class KmsKeyConfiguration(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "kms_key_configurations"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[KmsProviderType] = mapped_column(
        Enum(KmsProviderType, name="kmsprovidertype", native_enum=True),
        nullable=False,
        default=KmsProviderType.LOCAL,
    )
    key_arn_or_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dek_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rotation_schedule_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_kms_configs_tenant_active", "tenant_id", "is_active"),)


class TenantDataResidency(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "tenant_data_residencies"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    region: Mapped[DataResidencyRegion] = mapped_column(
        Enum(DataResidencyRegion, name="dataresidencyregion", native_enum=True),
        nullable=False,
        default=DataResidencyRegion.US_EAST,
        index=True,
    )
    enforce_strict: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    database_schema: Mapped[str] = mapped_column(String(128), default="public", nullable=False)
    qdrant_collection_prefix: Mapped[str] = mapped_column(String(128), default="titan", nullable=False)

    __table_args__ = (Index("ix_residency_tenant_region", "tenant_id", "region"),)


class QuarantineFileLog(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "quarantine_file_logs"

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
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    threat_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quarantine_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    scanner_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_quarantine_tenant_created", "tenant_id", "created_at"),
        Index("ix_quarantine_sha256", "content_hash_sha256"),
    )
