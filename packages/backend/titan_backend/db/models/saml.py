from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SAMLConfiguration(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "saml_configurations"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    idp_entity_id: Mapped[str] = mapped_column(String(512), nullable=False)
    idp_sso_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    idp_x509_cert: Mapped[str] = mapped_column(Text, nullable=False)
    sp_entity_id: Mapped[str] = mapped_column(String(512), nullable=False)
    sp_acs_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    attribute_mapping: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=lambda: {
            "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "groups": "http://schemas.xmlsoap.org/claims/Group",
        },
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_unencrypted_assertions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_saml_configs_tenant_active", "tenant_id", "is_active"),)
