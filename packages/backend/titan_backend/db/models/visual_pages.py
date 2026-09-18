from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class VisualPage(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "visual_pages"

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
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entropy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_visual_qualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rendered_image_s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visual_features: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_visual_pages_doc_page", "document_id", "page_number", unique=True),
        Index("ix_visual_pages_workspace_qualified", "workspace_id", "is_visual_qualified"),
        Index("ix_visual_pages_tenant_workspace", "tenant_id", "workspace_id"),
    )
