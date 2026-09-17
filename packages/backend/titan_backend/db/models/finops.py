import enum
from typing import Any
from uuid import UUID

from sqlalchemy import Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class FinOpsOperation(str, enum.Enum):
    CHAT_FAST = "CHAT_FAST"
    CHAT_DEEP = "CHAT_DEEP"
    INGESTION_DOCLING = "INGESTION_DOCLING"
    INGESTION_EMBEDDING = "INGESTION_EMBEDDING"
    COLPALI_VISION = "COLPALI_VISION"
    RERANK = "RERANK"
    EVALUATION = "EVALUATION"


class FinOpsLedger(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "finops_ledger"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    operation_type: Mapped[FinOpsOperation] = mapped_column(
        Enum(FinOpsOperation), nullable=False, index=True
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gpu_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    compute_units: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dollar_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_finops_ledger_tenant_workspace_created", "tenant_id", "workspace_id", "created_at"),
        Index("ix_finops_ledger_operation_created", "operation_type", "created_at"),
    )
