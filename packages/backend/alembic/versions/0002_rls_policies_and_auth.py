"""Attach Row-Level Security policies and system worker role

Revision ID: 0002_rls_policies_and_auth
Revises: 0001_initial_schema
Create Date: 2026-09-14 12:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_rls_policies_and_auth"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = [
    "documents",
    "chunks",
    "chat_sessions",
    "api_keys",
    "acl_groups",
    "audit_log",
    "feedback",
    "connectors",
]


def upgrade() -> None:
    # 1. Attach tenant isolation RLS policy to all tenant-scoped tables
    for table in RLS_TABLES:
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

    # 2. Conditionally create system_worker role with BYPASSRLS for background tasks
    role_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'system_worker') THEN
            CREATE ROLE system_worker WITH LOGIN BYPASSRLS PASSWORD 'system_worker_dev_password';
        END IF;
    END $$;
    """
    op.execute(role_sql)


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
