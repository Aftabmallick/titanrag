"""Phase 9 Enterprise Compliance, Security Hardening & Operational Excellence

Revision ID: 0008_phase9_compliance_security
Revises: 0007_phase8_intelligence
Create Date: 2026-09-19 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_phase9_compliance_security"
down_revision: str | None = "0007_phase8_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create Enums if not exist
    enum_definitions = [
        ("gdprdeletionstatus", "('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')"),
        ("consentpurpose", "('TRAINING', 'ANALYTICS', 'THIRD_PARTY', 'NECESSARY')"),
        ("consentstatus", "('GRANTED', 'REVOKED')"),
        ("retentiontargetresource", "('CHAT_MESSAGES', 'SEMANTIC_CACHE', 'DOCUMENT_VERSIONS', 'AUDIT_LOGS')"),
        ("retentionaction", "('SOFT_DELETE', 'HARD_DELETE', 'ARCHIVE_COLD')"),
        ("kmsprovidertype", "('LOCAL', 'AWS_KMS', 'GCP_KMS', 'HASHICORP_VAULT')"),
        ("dataresidencyregion", "('US_EAST', 'US_WEST', 'EU_CENTRAL', 'EU_WEST', 'APAC_SOUTHEAST')"),
    ]

    for enum_name, enum_values in enum_definitions:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN "
            f"CREATE TYPE {enum_name} AS ENUM {enum_values}; END IF; END $$;"
        )

    # 2. Table: gdpr_deletion_requests
    op.create_table(
        "gdpr_deletion_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="gdprdeletionstatus", create_type=False
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "targets",
            postgresql.JSONB(),
            nullable=False,
            server_default='{"db": true, "qdrant": true, "minio": true, "redis": true}',
        ),
        sa.Column("audit_trail", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("verification_hash", sa.String(64), nullable=True),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_gdpr_requests_tenant_status", "gdpr_deletion_requests", ["tenant_id", "status"])
    op.create_index("ix_gdpr_requests_user", "gdpr_deletion_requests", ["tenant_id", "user_id"])

    # 3. Table: user_consents
    op.create_table(
        "user_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "purpose",
            postgresql.ENUM(
                "TRAINING", "ANALYTICS", "THIRD_PARTY", "NECESSARY", name="consentpurpose", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("GRANTED", "REVOKED", name="consentstatus", create_type=False),
            nullable=False,
            server_default="GRANTED",
        ),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="v1.0"),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_consents_tenant_user", "user_consents", ["tenant_id", "user_id"])
    op.create_index("ix_user_consents_lookup", "user_consents", ["tenant_id", "user_id", "purpose", "status"])

    # 4. Table: data_retention_policies
    op.create_table(
        "data_retention_policies",
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
            nullable=True,
            index=True,
        ),
        sa.Column(
            "target_resource",
            postgresql.ENUM(
                "CHAT_MESSAGES",
                "SEMANTIC_CACHE",
                "DOCUMENT_VERSIONS",
                "AUDIT_LOGS",
                name="retentiontargetresource",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("ttl_days", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM("SOFT_DELETE", "HARD_DELETE", "ARCHIVE_COLD", name="retentionaction", create_type=False),
            nullable=False,
            server_default="HARD_DELETE",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_retention_policies_tenant_ws", "data_retention_policies", ["tenant_id", "workspace_id"])
    op.create_index(
        "ix_retention_policies_resource", "data_retention_policies", ["tenant_id", "target_resource", "is_active"]
    )

    # 5. Table: retention_audit_logs
    op.create_table(
        "retention_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_retention_policies.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "resource_type",
            postgresql.ENUM(
                "CHAT_MESSAGES",
                "SEMANTIC_CACHE",
                "DOCUMENT_VERSIONS",
                "AUDIT_LOGS",
                name="retentiontargetresource",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("records_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_purged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_reclaimed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_retention_audit_tenant_exec", "retention_audit_logs", ["tenant_id", "executed_at"])

    # 6. Table: kms_key_configurations
    op.create_table(
        "kms_key_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "LOCAL", "AWS_KMS", "GCP_KMS", "HASHICORP_VAULT", name="kmsprovidertype", create_type=False
            ),
            nullable=False,
            server_default="LOCAL",
        ),
        sa.Column("key_arn_or_path", sa.String(1024), nullable=False),
        sa.Column("encrypted_dek", sa.LargeBinary(), nullable=False),
        sa.Column("dek_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rotation_schedule_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_kms_configs_tenant_active", "kms_key_configurations", ["tenant_id", "is_active"])

    # 7. Table: tenant_data_residencies
    op.create_table(
        "tenant_data_residencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "region",
            postgresql.ENUM(
                "US_EAST",
                "US_WEST",
                "EU_CENTRAL",
                "EU_WEST",
                "APAC_SOUTHEAST",
                name="dataresidencyregion",
                create_type=False,
            ),
            nullable=False,
            server_default="US_EAST",
        ),
        sa.Column("enforce_strict", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("storage_bucket", sa.String(255), nullable=False),
        sa.Column("database_schema", sa.String(128), nullable=False, server_default="public"),
        sa.Column("qdrant_collection_prefix", sa.String(128), nullable=False, server_default="titan"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_residency_tenant_region", "tenant_data_residencies", ["tenant_id", "region"])

    # 8. Table: quarantine_file_logs
    op.create_table(
        "quarantine_file_logs",
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
            nullable=True,
            index=True,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_hash_sha256", sa.String(64), nullable=False, index=True),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("threat_name", sa.String(255), nullable=False),
        sa.Column("quarantine_path", sa.String(1024), nullable=False),
        sa.Column("scanner_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quarantine_tenant_created", "quarantine_file_logs", ["tenant_id", "created_at"])
    op.create_index("ix_quarantine_sha256", "quarantine_file_logs", ["content_hash_sha256"])

    # 9. Enable Row-Level Security (RLS) on all 7 tables
    rls_tables = [
        "gdpr_deletion_requests",
        "user_consents",
        "data_retention_policies",
        "retention_audit_logs",
        "kms_key_configurations",
        "tenant_data_residencies",
        "quarantine_file_logs",
    ]
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
    tables = [
        "quarantine_file_logs",
        "tenant_data_residencies",
        "kms_key_configurations",
        "retention_audit_logs",
        "data_retention_policies",
        "user_consents",
        "gdpr_deletion_requests",
    ]
    for table in tables:
        op.drop_table(table)

    enums = [
        "dataresidencyregion",
        "kmsprovidertype",
        "retentionaction",
        "retentiontargetresource",
        "consentstatus",
        "consentpurpose",
        "gdprdeletionstatus",
    ]
    for enum_name in enums:
        op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE;")
