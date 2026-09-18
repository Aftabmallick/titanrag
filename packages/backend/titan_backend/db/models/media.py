import enum
from typing import Any
from uuid import UUID

from sqlalchemy import Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MediaTranscriptionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MediaTranscription(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "media_transcriptions"

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
        unique=True,
        index=True,
    )
    media_type: Mapped[str] = mapped_column(String(50), nullable=False)  # audio/mpeg, video/mp4, etc.
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    speaker_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[MediaTranscriptionStatus] = mapped_column(
        Enum(MediaTranscriptionStatus),
        default=MediaTranscriptionStatus.PENDING,
        nullable=False,
        index=True,
    )
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    full_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_media_transcriptions_workspace_status", "workspace_id", "status"),
        Index("ix_media_transcriptions_tenant_workspace", "tenant_id", "workspace_id"),
    )
