"""Phase 4 RAG Settings Evolution

Revision ID: 0004_phase4_rag_settings
Revises: 0003_phase3_ingestion_schema
Create Date: 2026-09-14 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase4_rag_settings"
down_revision: str | None = "0003_phase3_ingestion_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rag_settings", sa.Column("parent_context_enabled", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("rag_settings", sa.Column("hyde_enabled", sa.Boolean(), server_default="false", nullable=False))
    op.add_column(
        "rag_settings", sa.Column("semantic_cache_enabled", sa.Boolean(), server_default="true", nullable=False)
    )
    op.add_column(
        "rag_settings", sa.Column("cache_cosine_threshold", sa.Float(), server_default="0.95", nullable=False)
    )
    op.add_column("rag_settings", sa.Column("cache_ttl_seconds", sa.Integer(), server_default="86400", nullable=False))
    op.add_column("rag_settings", sa.Column("system_prompt_override", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rag_settings", "system_prompt_override")
    op.drop_column("rag_settings", "cache_ttl_seconds")
    op.drop_column("rag_settings", "cache_cosine_threshold")
    op.drop_column("rag_settings", "semantic_cache_enabled")
    op.drop_column("rag_settings", "hyde_enabled")
    op.drop_column("rag_settings", "parent_context_enabled")
