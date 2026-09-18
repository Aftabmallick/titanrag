import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class HookType(str, enum.Enum):
    ON_PARSE = "ON_PARSE"
    ON_CHUNK = "ON_CHUNK"
    ON_EMBED = "ON_EMBED"
    ON_RERANK = "ON_RERANK"
    ON_POST_GENERATE = "ON_POST_GENERATE"


class PluginHealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class Plugin(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """
    Registered external webhook micro-hook extension for TitanRAG.
    Enables safe out-of-process custom parsers, chunkers, rerankers, and egress filters.
    """

    __tablename__ = "plugins"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)

    # HTTPS endpoint where hook payloads will be dispatched via POST
    endpoint_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # 256-bit hexadecimal secret for HMAC-SHA256 request signing (never exposed in public API)
    webhook_secret: Mapped[str] = mapped_column(String(255), nullable=False)

    # Array of HookType strings enabled for this plugin, e.g. ["ON_PARSE", "ON_POST_GENERATE"]
    hooks: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Per-hook execution timeout budget in milliseconds (default 2000ms)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Operational health tracking
    health_status: Mapped[PluginHealthStatus] = mapped_column(
        Enum(PluginHealthStatus), default=PluginHealthStatus.HEALTHY, nullable=False
    )
    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    circuit_tripped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    circuit_tripped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    execution_logs: Mapped[list["PluginExecutionLog"]] = relationship(
        "PluginExecutionLog",
        back_populates="plugin",
        cascade="all, delete-orphan",
        order_by="desc(PluginExecutionLog.timestamp)",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_plugins_workspace_slug"),
        Index("ix_plugins_workspace_active", "workspace_id", "is_active"),
        Index("ix_plugins_tenant_workspace", "tenant_id", "workspace_id"),
    )


class PluginExecutionLog(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """
    Granular audit log of an external micro-hook execution.
    Captures status code, latency, and sample payload digests.
    """

    __tablename__ = "plugin_execution_logs"

    plugin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hook_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    request_payload_sample: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_payload_sample: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    plugin: Mapped["Plugin"] = relationship("Plugin", back_populates="execution_logs")

    __table_args__ = (
        Index("ix_plugin_logs_plugin_timestamp", "plugin_id", "timestamp"),
        Index("ix_plugin_logs_tenant_workspace", "tenant_id", "workspace_id"),
    )
