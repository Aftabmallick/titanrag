import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ABExperimentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CONCLUDED = "CONCLUDED"
    ROLLED_BACK = "ROLLED_BACK"


class ABExperiment(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "ab_experiments"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ABExperimentStatus] = mapped_column(
        Enum(ABExperimentStatus), default=ABExperimentStatus.DRAFT, nullable=False, index=True
    )
    traffic_split: Mapped[int] = mapped_column(Integer, default=50, nullable=False)  # 0 to 100 (% Treatment)
    control_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    treatment_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    sample_size_control: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sample_size_treatment: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(100), default="SATISFACTION_RATE", nullable=False)
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    statistical_significance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    winning_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)  # CONTROL, TREATMENT, INCONCLUSIVE
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_ab_experiments_workspace_status", "workspace_id", "status"),)
