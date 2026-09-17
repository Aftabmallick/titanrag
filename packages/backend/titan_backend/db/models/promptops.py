import enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PromptEnvironment(str, enum.Enum):
    DEV = "DEV"
    STAGING = "STAGING"
    PROD = "PROD"


class PromptTemplate(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "prompt_templates"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    versions: Mapped[list["PromptVersion"]] = relationship(
        "PromptVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="desc(PromptVersion.version_number)",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_prompt_templates_workspace_slug"),
        Index("ix_prompt_templates_workspace_slug", "workspace_id", "slug"),
    )


class PromptVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_versions"

    template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    environment: Mapped[PromptEnvironment] = mapped_column(
        Enum(PromptEnvironment), default=PromptEnvironment.DEV, nullable=False, index=True
    )
    author_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    commit_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_count_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    template: Mapped[PromptTemplate] = relationship("PromptTemplate", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_prompt_version_template_num"),
        Index("ix_prompt_versions_template_env_active", "template_id", "environment", "is_active"),
    )
