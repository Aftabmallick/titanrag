"""Phase 7 Plugin Registry and Micro-Hook Execution Logs Schema

Revision ID: 0006_phase7_plugins_tables
Revises: 0005_phase6_llmops_tables
Create Date: 2026-09-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase7_plugins_tables"
down_revision: str | None = "0005_phase6_llmops_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    health_status_enum = sa.Enum("HEALTHY", "DEGRADED", "OFFLINE", name="pluginhealthstatus")
    health_status_enum.create(op.get_bind(), checkfirst=True)

    # 1. Create plugins table
    op.create_table(
        "plugins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0.0"),
        sa.Column("endpoint_url", sa.String(1024), nullable=False),
        sa.Column("webhook_secret", sa.String(255), nullable=False),
        sa.Column("hooks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("timeout_ms", sa.Integer(), nullable=False, server_default="2000"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("health_status", health_status_enum, nullable=False, server_default="HEALTHY"),
        sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("circuit_tripped", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("circuit_tripped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_plugins_workspace_slug"),
    )
    op.create_index("ix_plugins_workspace_active", "plugins", ["workspace_id", "is_active"])
    op.create_index("ix_plugins_tenant_workspace", "plugins", ["tenant_id", "workspace_id"])

    # 2. Create plugin_execution_logs table
    op.create_table(
        "plugin_execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "plugin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("plugins.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("hook_type", sa.String(50), nullable=False, index=True),
        sa.Column("request_id", sa.String(255), nullable=True, index=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("request_payload_sample", postgresql.JSONB(), nullable=True),
        sa.Column("response_payload_sample", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_plugin_logs_plugin_timestamp", "plugin_execution_logs", ["plugin_id", "timestamp"])
    op.create_index("ix_plugin_logs_tenant_workspace", "plugin_execution_logs", ["tenant_id", "workspace_id"])

    # 3. Enable RLS and attach tenant isolation policies
    for table in ["plugins", "plugin_execution_logs"]:
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
    op.drop_table("plugin_execution_logs")
    op.drop_table("plugins")
    op.execute("DROP TYPE IF EXISTS pluginhealthstatus")
