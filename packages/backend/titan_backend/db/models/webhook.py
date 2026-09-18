from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Webhook(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "webhooks"

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
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret_token: Mapped[str] = mapped_column(String(255), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    delivery_logs: Mapped[list["WebhookDeliveryLog"]] = relationship(
        "WebhookDeliveryLog", back_populates="webhook", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_webhooks_workspace_active", "workspace_id", "is_active"),
        Index("ix_webhooks_tenant_workspace", "tenant_id", "workspace_id"),
    )


class WebhookDeliveryLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "webhook_delivery_logs"

    webhook_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    webhook: Mapped["Webhook"] = relationship("Webhook", back_populates="delivery_logs")

    __table_args__ = (
        Index("ix_webhook_delivery_logs_webhook_event", "webhook_id", "event_type"),
        Index("ix_webhook_delivery_logs_delivered_at", "delivered_at"),
    )
