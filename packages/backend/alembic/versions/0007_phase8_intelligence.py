"""Phase 8 Enterprise Intelligence Schema (SAML, Webhooks, Media Transcriptions, Visual Pages, CDC Connectors)

Revision ID: 0007_phase8_intelligence
Revises: 0006_phase7_plugins_tables
Create Date: 2026-09-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase8_intelligence"
down_revision: str | None = "0006_phase7_plugins_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create Enums if not exist
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mediatranscriptionstatus') THEN "
        "CREATE TYPE mediatranscriptionstatus AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'); END IF; END $$;"
    )
    media_status_enum = postgresql.ENUM(
        "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="mediatranscriptionstatus", create_type=False
    )

    # 2. Add CDC and ACL mapping columns to connectors
    op.add_column("connectors", sa.Column("cdc_cursor", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("connectors", sa.Column("last_sync_error", sa.Text(), nullable=True))
    op.add_column(
        "connectors", sa.Column("source_acl_mapping", postgresql.JSONB(), nullable=False, server_default="{}")
    )
    op.add_column("connectors", sa.Column("sync_stats", postgresql.JSONB(), nullable=False, server_default="{}"))

    # 3. Create saml_configurations table
    op.create_table(
        "saml_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("idp_entity_id", sa.String(512), nullable=False),
        sa.Column("idp_sso_url", sa.String(1024), nullable=False),
        sa.Column("idp_x509_cert", sa.Text(), nullable=False),
        sa.Column("sp_entity_id", sa.String(512), nullable=False),
        sa.Column("sp_acs_url", sa.String(1024), nullable=False),
        sa.Column(
            "attribute_mapping",
            postgresql.JSONB(),
            nullable=False,
            server_default='{"email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name", "groups": "http://schemas.xmlsoap.org/claims/Group"}',
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_unencrypted_assertions", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saml_configs_tenant_active", "saml_configurations", ["tenant_id", "is_active"])

    # 4. Create webhooks table
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("secret_token", sa.String(255), nullable=False),
        sa.Column("events", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_webhooks_workspace_active", "webhooks", ["workspace_id", "is_active"])
    op.create_index("ix_webhooks_tenant_workspace", "webhooks", ["tenant_id", "workspace_id"])

    # 5. Create webhook_delivery_logs table
    op.create_table(
        "webhook_delivery_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_webhook_delivery_logs_webhook_event", "webhook_delivery_logs", ["webhook_id", "event_type"])

    # 6. Create media_transcriptions table
    op.create_table(
        "media_transcriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("media_type", sa.String(50), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("speaker_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", media_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("segments", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("full_transcript", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_media_transcriptions_workspace_status", "media_transcriptions", ["workspace_id", "status"])
    op.create_index("ix_media_transcriptions_tenant_workspace", "media_transcriptions", ["tenant_id", "workspace_id"])

    # 7. Create visual_pages table
    op.create_table(
        "visual_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("entropy_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_visual_qualified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rendered_image_s3_key", sa.String(1024), nullable=False),
        sa.Column("qdrant_point_id", sa.String(64), nullable=True),
        sa.Column("visual_features", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "page_number", name="uq_visual_pages_doc_page"),
    )
    op.create_index("ix_visual_pages_workspace_qualified", "visual_pages", ["workspace_id", "is_visual_qualified"])
    op.create_index("ix_visual_pages_tenant_workspace", "visual_pages", ["tenant_id", "workspace_id"])

    # 8. Enable RLS and attach tenant isolation policies
    rls_tables = ["saml_configurations", "webhooks", "media_transcriptions", "visual_pages"]
    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        policy_sql = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies 
                WHERE tablename = '{table}' AND policyname = 'tenant_isolation_policy'
            ) THEN
                CREATE POLICY tenant_isolation_policy ON {table}
                AS RESTRICTIVE
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            END IF;
        END $$;
        """
        op.execute(policy_sql)


def downgrade() -> None:
    op.drop_table("visual_pages")
    op.drop_table("media_transcriptions")
    op.drop_table("webhook_delivery_logs")
    op.drop_table("webhooks")
    op.drop_table("saml_configurations")

    op.drop_column("connectors", "sync_stats")
    op.drop_column("connectors", "source_acl_mapping")
    op.drop_column("connectors", "last_sync_error")
    op.drop_column("connectors", "cdc_cursor")

    op.execute("DROP TYPE IF EXISTS mediatranscriptionstatus CASCADE")
