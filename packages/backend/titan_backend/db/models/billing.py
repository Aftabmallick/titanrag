"""Phase 10 — Billing, White-Label & Sandbox DB Models.

Covers:
- StripeCustomer: tenant → Stripe customer/subscription mapping
- BillingEvent: idempotent Stripe webhook event log
- TenantBrandConfig: per-tenant white-label branding configuration
- BatchJob: async batch query/upload/delete job tracking
- SandboxSession: ephemeral no-sign-up demo sessions
- SystemAnnouncement: platform-wide broadcast messages
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from titan_backend.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

# ---------------------------------------------------------------------------
# Stripe Billing Enums
# ---------------------------------------------------------------------------


class StripePlanSlug(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"
    SANDBOX = "SANDBOX"


class StripeSubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    TRIALING = "TRIALING"
    INCOMPLETE = "INCOMPLETE"
    READ_ONLY = "READ_ONLY"  # payment failed — soft limit


class BatchJobType(str, enum.Enum):
    QUERY = "QUERY"
    UPLOAD = "UPLOAD"
    DELETE = "DELETE"


class BatchJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class AnnouncementSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# StripeCustomer — tenant ↔ Stripe account mapping
# ---------------------------------------------------------------------------


class StripeCustomer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Maps a TitanRAG tenant to a Stripe Customer and Subscription."""

    __tablename__ = "stripe_customers"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
    )
    plan_slug: Mapped[StripePlanSlug] = mapped_column(
        Enum(StripePlanSlug, name="stripeplanslug", native_enum=True),
        nullable=False,
        default=StripePlanSlug.FREE,
        index=True,
    )
    subscription_status: Mapped[StripeSubscriptionStatus] = mapped_column(
        Enum(StripeSubscriptionStatus, name="stripesubscriptionstatus", native_enum=True),
        nullable=False,
        default=StripeSubscriptionStatus.ACTIVE,
        index=True,
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Monthly CU allocation for this plan (configurable override for enterprise)
    cu_monthly_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,  # FREE default
    )
    # Overage rate in USD cents per CU (0 = hard stop, no overage)
    cu_overage_rate_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    # Stripe billing customer email (for receipts)
    billing_email: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        Index("ix_stripe_customers_tenant", "tenant_id"),
        Index("ix_stripe_customers_plan_status", "plan_slug", "subscription_status"),
    )


# ---------------------------------------------------------------------------
# BillingEvent — idempotent Stripe webhook event log
# ---------------------------------------------------------------------------


class BillingEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Idempotent log of all processed Stripe webhook events.

    The unique constraint on stripe_event_id ensures that if Stripe
    delivers the same event twice, the second delivery is silently
    dropped at the DB level.
    """

    __tablename__ = "billing_events"

    # No tenant_id — events are global; tenant resolved via stripe_customer_id
    stripe_event_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="Stripe event ID — idempotency key",
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_billing_events_type_created", "event_type", "created_at"),
        Index("ix_billing_events_customer", "stripe_customer_id"),
    )


# ---------------------------------------------------------------------------
# TenantBrandConfig — white-label branding per tenant
# ---------------------------------------------------------------------------


class TenantBrandConfig(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Per-tenant white-label branding configuration.

    Stored and served from backend; Next.js middleware injects CSS vars.
    Asset URLs point to MinIO presigned URLs.
    """

    __tablename__ = "tenant_brand_configs"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(128), nullable=False, default="TitanRAG")
    # MinIO object keys (paths, not presigned URLs — presigned at serve time)
    logo_light_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logo_dark_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    favicon_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Brand colors — hex (#RRGGBB), validated before store
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    accent_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#8b5cf6")
    # Custom domain (unique across all tenants)
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    # Domain verification status
    domain_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    domain_verification_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Email sending config (optional override)
    from_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_brand_configs_tenant", "tenant_id"),
        Index("ix_brand_configs_custom_domain", "custom_domain"),
    )


# ---------------------------------------------------------------------------
# BatchJob — async batch query/upload/delete job tracking
# ---------------------------------------------------------------------------


class BatchJob(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Tracks async batch API jobs (queries, uploads, deletes).

    The Celery task updates `completed_items`, `failed_items`, and `status`
    as it processes items. On completion, fires a webhook if configured.
    """

    __tablename__ = "batch_jobs"

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
    job_type: Mapped[BatchJobType] = mapped_column(
        Enum(BatchJobType, name="batchjobtype", native_enum=True),
        nullable=False,
        index=True,
    )
    status: Mapped[BatchJobStatus] = mapped_column(
        Enum(BatchJobStatus, name="batchjobstatus", native_enum=True),
        nullable=False,
        default=BatchJobStatus.PENDING,
        index=True,
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Input items (queries list, document IDs, etc.)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Output results summary (populated on completion)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Webhook delivery config
    webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    webhook_delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Celery task ID for monitoring
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_batch_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_batch_jobs_workspace_created", "workspace_id", "created_at"),
        Index("ix_batch_jobs_celery", "celery_task_id"),
    )


# ---------------------------------------------------------------------------
# SandboxSession — ephemeral no-signup demo sessions
# ---------------------------------------------------------------------------


class SandboxSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Ephemeral sandbox session — no tenant account required.

    Each session gets a temporary tenant_id, workspace_id, and user_id.
    Sessions auto-expire after 24 hours. Cleanup job purges all associated
    data from Postgres, Qdrant (payload filter), MinIO, and Redis.
    """

    __tablename__ = "sandbox_sessions"

    # Ephemeral tenant/workspace/user created for this session
    ephemeral_tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    ephemeral_workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    ephemeral_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    # JWT access token for the ephemeral user (short-lived)
    access_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Client identification for rate limiting
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Session lifecycle
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_purged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Usage tracking (for rate limiting)
    query_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    upload_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Onboarding tour step tracking
    tour_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_sandbox_sessions_expires", "expires_at", "is_purged"),
        Index("ix_sandbox_sessions_ip", "client_ip", "created_at"),
        Index("ix_sandbox_sessions_tenant", "ephemeral_tenant_id"),
    )


# ---------------------------------------------------------------------------
# SystemAnnouncement — platform-wide broadcast messages
# ---------------------------------------------------------------------------


class SystemAnnouncement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform-wide announcements displayed as banners to all tenants.

    Created by platform admins. Stored in DB and mirrored to Redis
    for fast read. Expires automatically based on `expires_at`.
    """

    __tablename__ = "system_announcements"

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[AnnouncementSeverity] = mapped_column(
        Enum(AnnouncementSeverity, name="announcementseverity", native_enum=True),
        nullable=False,
        default=AnnouncementSeverity.INFO,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Optional: target specific tenants (null = all tenants)
    target_tenant_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # Link (optional — e.g., status page, docs)
    action_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    action_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_announcements_active_expires", "is_active", "expires_at"),
        Index("ix_announcements_severity", "severity", "is_active"),
    )
