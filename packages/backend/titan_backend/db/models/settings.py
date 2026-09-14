from uuid import UUID

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RAGSettings(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "rag_settings"

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
    retrieval_mode: Mapped[str] = mapped_column(String(50), default="HYBRID", nullable=False)
    dense_weight: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    sparse_weight: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    rerank_top_k: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    score_threshold: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    context_window_strategy: Mapped[str] = mapped_column(String(50), default="HIERARCHICAL", nullable=False)

    __table_args__ = (Index("ix_rag_settings_workspace_unique", "workspace_id", unique=True),)
