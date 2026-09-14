"""Phase 3 Ingestion Schema Evolution

Revision ID: 0002_phase3_ingestion_schema
Revises: 0001_initial_schema
Create Date: 2026-09-14 13:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase3_ingestion_schema"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Expand documentstatus enum in PostgreSQL if postgres dialect
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for val in ["PARSED", "REDACTED", "CHUNKED", "EMBEDDED", "READY", "ARCHIVED", "DELETING"]:
            op.execute(sa.text(f"ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS '{val}'"))

    # 2. Documents table updates
    op.add_column("documents", sa.Column("doc_type", sa.String(50), server_default="generic", nullable=False))
    op.add_column("documents", sa.Column("folder", sa.String(255), nullable=True))
    op.add_column(
        "documents", sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False)
    )
    op.add_column("documents", sa.Column("is_stale", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("documents", sa.Column("staleness_ttl_days", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("is_shared", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("documents", sa.Column("shared_from_workspace_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_index("ix_documents_workspace_folder", "documents", ["workspace_id", "folder"])

    # 3. Chunks table updates
    op.add_column("chunks", sa.Column("minhash_signature", sa.String(64), nullable=True))
    op.add_column("chunks", sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False))

    # 4. Ingestion tasks table updates
    op.add_column("ingestion_tasks", sa.Column("total_chunks", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ingestion_tasks", sa.Column("processed_chunks", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "ingestion_tasks",
        sa.Column("checkpoint_data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ingestion_tasks", "checkpoint_data")
    op.drop_column("ingestion_tasks", "processed_chunks")
    op.drop_column("ingestion_tasks", "total_chunks")

    op.drop_column("chunks", "is_active")
    op.drop_column("chunks", "minhash_signature")

    op.drop_index("ix_documents_workspace_folder", "documents")
    op.drop_column("documents", "shared_from_workspace_id")
    op.drop_column("documents", "is_shared")
    op.drop_column("documents", "staleness_ttl_days")
    op.drop_column("documents", "is_stale")
    op.drop_column("documents", "tags")
    op.drop_column("documents", "folder")
    op.drop_column("documents", "doc_type")
