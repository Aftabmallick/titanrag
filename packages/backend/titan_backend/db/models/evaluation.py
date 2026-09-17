import enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvaluationTrigger(str, enum.Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    CI_CD = "CI_CD"
    FLYWHEEL = "FLYWHEEL"


class GoldenDataset(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "golden_datasets"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list["GoldenDatasetItem"]] = relationship(
        "GoldenDatasetItem",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="GoldenDatasetItem.created_at",
    )

    __table_args__ = (Index("ix_golden_datasets_tenant_workspace", "tenant_id", "workspace_id"),)


class GoldenDatasetItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "golden_dataset_items"

    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("golden_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_chunk_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    expected_document_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    metadata_filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    dataset: Mapped[GoldenDataset] = relationship("GoldenDataset", back_populates="items")


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "evaluation_runs"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("golden_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rag_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus), default=EvaluationStatus.PENDING, nullable=False, index=True
    )
    triggered_by: Mapped[EvaluationTrigger] = mapped_column(
        Enum(EvaluationTrigger), default=EvaluationTrigger.MANUAL, nullable=False
    )
    aggregate_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    latency_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    total_compute_units: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_dollar_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    results: Mapped[list["EvaluationResultItem"]] = relationship(
        "EvaluationResultItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_evaluation_runs_workspace_created", "workspace_id", "created_at"),)


class EvaluationResultItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evaluation_result_items"

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("golden_dataset_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_cu: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[EvaluationRun] = relationship("EvaluationRun", back_populates="results")
