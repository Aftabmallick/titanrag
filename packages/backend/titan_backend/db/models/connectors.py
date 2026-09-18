import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ConnectorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class SyncStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Connector(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "connectors"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "gdrive", "sharepoint", "notion"
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus),
        default=ConnectorStatus.ACTIVE,
        nullable=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    auth_credentials: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    sync_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)  # cron expression
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cdc_cursor: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_acl_mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    sync_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    sync_logs: Mapped[list["ConnectorSyncLog"]] = relationship(
        "ConnectorSyncLog", back_populates="connector", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_connectors_tenant_workspace", "tenant_id", "workspace_id"),
        Index("ix_connectors_type_status", "connector_type", "status"),
    )


class ConnectorSyncLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connector_sync_log"

    connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus),
        default=SyncStatus.RUNNING,
        nullable=False,
        index=True,
    )
    documents_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connector: Mapped["Connector"] = relationship("Connector", back_populates="sync_logs")

    __table_args__ = (Index("ix_connector_sync_log_conn_status", "connector_id", "status"),)
