from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ACLGroup(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "acl_groups"

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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    members: Mapped[list["ACLGroupMember"]] = relationship(
        "ACLGroupMember", back_populates="group", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_acl_groups_workspace_name", "workspace_id", "name", unique=True),)


class ACLGroupMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "acl_group_members"

    group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("acl_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    group: Mapped["ACLGroup"] = relationship("ACLGroup", back_populates="members")

    __table_args__ = (Index("ix_acl_group_user_unique", "group_id", "user_id", unique=True),)


class DocumentACL(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_acl"

    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("acl_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission: Mapped[str] = mapped_column(String(50), default="READ", nullable=False)

    __table_args__ = (Index("ix_doc_acl_unique", "document_id", "group_id", unique=True),)
