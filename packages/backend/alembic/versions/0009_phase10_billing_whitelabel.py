"""Phase 10 — Alembic Migration 0009: Billing, White-Label & Sandbox Tables.

Creates:
- stripe_customers         (tenant ↔ Stripe customer/subscription)
- billing_events           (idempotent Stripe webhook event log)
- tenant_brand_configs     (per-tenant white-label branding)
- batch_jobs               (async batch API job tracking)
- sandbox_sessions         (ephemeral no-signup demo sessions)
- system_announcements     (platform-wide broadcast messages)

Revision ID: 0009_phase10_billing_whitelabel
Revises: 0008_phase9_compliance_security
Create Date: 2026-09-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_phase10_billing_whitelabel"
down_revision: str | None = "0008_phase9_compliance_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Create Enums
    # -----------------------------------------------------------------------
    enum_definitions = [
        ("stripeplanslug", "('FREE', 'PRO', 'ENTERPRISE', 'SANDBOX')"),
        (
            "stripesubscriptionstatus",
            "('ACTIVE', 'PAST_DUE', 'CANCELED', 'TRIALING', 'INCOMPLETE', 'READ_ONLY')",
        ),
        ("batchjobtype", "('QUERY', 'UPLOAD', 'DELETE')"),
        (
            "batchjobstatus",
            "('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'PARTIALLY_COMPLETED')",
        ),
        ("announcementseverity", "('INFO', 'WARNING', 'CRITICAL')"),
    ]
    for enum_name, values in enum_definitions:
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {enum_name} AS ENUM {values}; EXCEPTION WHEN duplicate_object THEN null; END $$;"
        )

    # -----------------------------------------------------------------------
    # 2. stripe_customers
    # -----------------------------------------------------------------------
    op.create_table(
        "stripe_customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True, unique=True),
        sa.Column(
            "plan_slug",
            postgresql.ENUM("FREE", "PRO", "ENTERPRISE", "SANDBOX", name="stripeplanslug", create_type=False),
            nullable=False,
            server_default="FREE",
        ),
        sa.Column(
            "subscription_status",
            postgresql.ENUM(
                "ACTIVE",
                "PAST_DUE",
                "CANCELED",
                "TRIALING",
                "INCOMPLETE",
                "READ_ONLY",
                name="stripesubscriptionstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cu_monthly_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("cu_overage_rate_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billing_email", sa.String(256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_stripe_customers_tenant", "stripe_customers", ["tenant_id"])
    op.create_index(
        "ix_stripe_customers_plan_status",
        "stripe_customers",
        ["plan_slug", "subscription_status"],
    )
    op.create_index("ix_stripe_customers_stripe_id", "stripe_customers", ["stripe_customer_id"])

    # -----------------------------------------------------------------------
    # 3. billing_events (idempotent Stripe webhook event log)
    # -----------------------------------------------------------------------
    op.create_table(
        "billing_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stripe_event_id", sa.String(128), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_billing_events_type_created", "billing_events", ["event_type", "created_at"])
    op.create_index("ix_billing_events_customer", "billing_events", ["stripe_customer_id"])

    # -----------------------------------------------------------------------
    # 4. tenant_brand_configs
    # -----------------------------------------------------------------------
    op.create_table(
        "tenant_brand_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("company_name", sa.String(128), nullable=False, server_default="TitanRAG"),
        sa.Column("logo_light_key", sa.String(512), nullable=True),
        sa.Column("logo_dark_key", sa.String(512), nullable=True),
        sa.Column("favicon_key", sa.String(512), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("accent_color", sa.String(7), nullable=False, server_default="#8b5cf6"),
        sa.Column("custom_domain", sa.String(255), nullable=True, unique=True),
        sa.Column("domain_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("domain_verification_token", sa.String(64), nullable=True),
        sa.Column("from_email", sa.String(256), nullable=True),
        sa.Column("from_name", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_brand_configs_tenant", "tenant_brand_configs", ["tenant_id"])
    op.create_index("ix_brand_configs_custom_domain", "tenant_brand_configs", ["custom_domain"])

    # -----------------------------------------------------------------------
    # 5. batch_jobs
    # -----------------------------------------------------------------------
    op.create_table(
        "batch_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_type",
            postgresql.ENUM("QUERY", "UPLOAD", "DELETE", name="batchjobtype", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "PROCESSING",
                "COMPLETED",
                "FAILED",
                "PARTIALLY_COMPLETED",
                name="batchjobstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("results", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("webhook_url", sa.String(1024), nullable=True),
        sa.Column("webhook_delivered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("webhook_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(128), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_batch_jobs_tenant_status", "batch_jobs", ["tenant_id", "status"])
    op.create_index("ix_batch_jobs_workspace_created", "batch_jobs", ["workspace_id", "created_at"])
    op.create_index("ix_batch_jobs_celery", "batch_jobs", ["celery_task_id"])

    # -----------------------------------------------------------------------
    # 6. sandbox_sessions
    # -----------------------------------------------------------------------
    op.create_table(
        "sandbox_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ephemeral_tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ephemeral_workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ephemeral_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token_hash", sa.String(64), nullable=False),
        sa.Column("client_ip", sa.String(64), nullable=False),
        sa.Column("client_fingerprint", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_purged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upload_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tour_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_sandbox_sessions_expires", "sandbox_sessions", ["expires_at", "is_purged"])
    op.create_index("ix_sandbox_sessions_ip", "sandbox_sessions", ["client_ip", "created_at"])
    op.create_index("ix_sandbox_sessions_tenant", "sandbox_sessions", ["ephemeral_tenant_id"])

    # -----------------------------------------------------------------------
    # 7. system_announcements
    # -----------------------------------------------------------------------
    op.create_table(
        "system_announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM("INFO", "WARNING", "CRITICAL", name="announcementseverity", create_type=False),
            nullable=False,
            server_default="INFO",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("target_tenant_ids", postgresql.JSONB(), nullable=True),
        sa.Column("action_url", sa.String(512), nullable=True),
        sa.Column("action_label", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_announcements_active_expires",
        "system_announcements",
        ["is_active", "expires_at"],
    )
    op.create_index(
        "ix_announcements_severity",
        "system_announcements",
        ["severity", "is_active"],
    )

    # -----------------------------------------------------------------------
    # 8. updated_at trigger for new tables
    # -----------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    tables_with_updated_at = [
        "stripe_customers",
        "billing_events",
        "tenant_brand_configs",
        "batch_jobs",
        "sandbox_sessions",
        "system_announcements",
    ]
    for table in tables_with_updated_at:
        op.execute(
            f"""
            CREATE OR REPLACE TRIGGER set_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    tables = [
        "system_announcements",
        "sandbox_sessions",
        "batch_jobs",
        "tenant_brand_configs",
        "billing_events",
        "stripe_customers",
    ]
    for table in tables:
        op.drop_table(table)

    # Drop enums
    for enum_name in [
        "announcementseverity",
        "batchjobstatus",
        "batchjobtype",
        "stripesubscriptionstatus",
        "stripeplanslug",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
