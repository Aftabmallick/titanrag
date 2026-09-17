import enum
from typing import Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class FeedbackTriageStatus(str, enum.Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    PROMOTED_TO_GOLDEN = "PROMOTED_TO_GOLDEN"
    IGNORED = "IGNORED"


class Feedback(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "feedback"

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
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 for thumbs up, -1 for thumbs down
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    triage_status: Mapped[FeedbackTriageStatus] = mapped_column(
        Enum(FeedbackTriageStatus), default=FeedbackTriageStatus.NEW, nullable=False, index=True
    )
    promoted_dataset_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("golden_dataset_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_feedback_tenant_workspace", "tenant_id", "workspace_id"),
        Index("ix_feedback_message_rating", "message_id", "rating"),
        Index("ix_feedback_workspace_triage", "workspace_id", "triage_status"),
    )
