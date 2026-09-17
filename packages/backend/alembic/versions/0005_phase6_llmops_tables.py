"""Phase 6 LLMOps, FinOps, PromptOps, Evaluation & Feedback Schema

Revision ID: 0005_phase6_llmops_tables
Revises: 0004_phase4_rag_settings
Create Date: 2026-09-17 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase6_llmops_tables"
down_revision: str | None = "0004_phase4_rag_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Golden Datasets & Items
    op.create_table(
        "golden_datasets",
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
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_golden_datasets_tenant_workspace", "golden_datasets", ["tenant_id", "workspace_id"])

    op.create_table(
        "golden_dataset_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golden_datasets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("expected_chunk_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("expected_document_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("metadata_filters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. Evaluation Runs & Results
    evaluation_status_enum = sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="evaluationstatus")
    evaluation_trigger_enum = sa.Enum("MANUAL", "SCHEDULED", "CI_CD", "FLYWHEEL", name="evaluationtrigger")

    op.create_table(
        "evaluation_runs",
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
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golden_datasets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rag_config_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", evaluation_status_enum, nullable=False, server_default="PENDING", index=True),
        sa.Column("triggered_by", evaluation_trigger_enum, nullable=False, server_default="MANUAL"),
        sa.Column("aggregate_scores", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("latency_stats", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("total_compute_units", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_dollar_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_runs_workspace_created", "evaluation_runs", ["workspace_id", "created_at"])

    op.create_table(
        "evaluation_result_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "dataset_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golden_dataset_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("generated_answer", sa.Text(), nullable=False),
        sa.Column("retrieved_chunk_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("scores", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cu", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. PromptOps Templates & Versions
    prompt_env_enum = sa.Enum("DEV", "STAGING", "PROD", name="promptenvironment")

    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_prompt_templates_workspace_slug"),
    )
    op.create_index("ix_prompt_templates_workspace_slug", "prompt_templates", ["workspace_id", "slug"])

    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("environment", prompt_env_enum, nullable=False, server_default="DEV", index=True),
        sa.Column(
            "author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("commit_message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("token_count_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("template_id", "version_number", name="uq_prompt_version_template_num"),
    )
    op.create_index(
        "ix_prompt_versions_template_env_active", "prompt_versions", ["template_id", "environment", "is_active"]
    )

    # 4. A/B Testing
    ab_status_enum = sa.Enum("DRAFT", "RUNNING", "PAUSED", "CONCLUDED", "ROLLED_BACK", name="abexperimentstatus")

    op.create_table(
        "ab_experiments",
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
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", ab_status_enum, nullable=False, server_default="DRAFT", index=True),
        sa.Column("traffic_split", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("control_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("treatment_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("sample_size_control", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sample_size_treatment", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("primary_metric", sa.String(100), nullable=False, server_default="SATISFACTION_RATE"),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("statistical_significance", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("winning_variant", sa.String(50), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ab_experiments_workspace_status", "ab_experiments", ["workspace_id", "status"])

    # 5. FinOps Ledger
    finops_op_enum = sa.Enum(
        "CHAT_FAST",
        "CHAT_DEEP",
        "INGESTION_DOCLING",
        "INGESTION_EMBEDDING",
        "COLPALI_VISION",
        "RERANK",
        "EVALUATION",
        name="finopsoperation",
    )

    op.create_table(
        "finops_ledger",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("request_id", sa.String(128), nullable=True, index=True),
        sa.Column("operation_type", finops_op_enum, nullable=False, index=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpu_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("compute_units", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("dollar_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_finops_ledger_tenant_workspace_created", "finops_ledger", ["tenant_id", "workspace_id", "created_at"]
    )
    op.create_index("ix_finops_ledger_operation_created", "finops_ledger", ["operation_type", "created_at"])

    # 6. Feedback table enhancements
    feedback_triage_enum = sa.Enum("NEW", "TRIAGED", "PROMOTED_TO_GOLDEN", "IGNORED", name="feedbacktriagestatus")
    feedback_triage_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("feedback", sa.Column("citation_issues", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("feedback", sa.Column("triage_status", feedback_triage_enum, nullable=False, server_default="NEW"))
    op.add_column(
        "feedback",
        sa.Column(
            "promoted_dataset_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golden_dataset_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_feedback_workspace_triage", "feedback", ["workspace_id", "triage_status"])


def downgrade() -> None:
    op.drop_index("ix_feedback_workspace_triage", table_name="feedback")
    op.drop_column("feedback", "promoted_dataset_item_id")
    op.drop_column("feedback", "triage_status")
    op.drop_column("feedback", "citation_issues")
    op.execute("DROP TYPE IF EXISTS feedbacktriagestatus")

    op.drop_table("finops_ledger")
    op.execute("DROP TYPE IF EXISTS finopsoperation")

    op.drop_table("ab_experiments")
    op.execute("DROP TYPE IF EXISTS abexperimentstatus")

    op.drop_table("prompt_versions")
    op.drop_table("prompt_templates")
    op.execute("DROP TYPE IF EXISTS promptenvironment")

    op.drop_table("evaluation_result_items")
    op.drop_table("evaluation_runs")
    op.execute("DROP TYPE IF EXISTS evaluationtrigger")
    op.execute("DROP TYPE IF EXISTS evaluationstatus")

    op.drop_table("golden_dataset_items")
    op.drop_table("golden_datasets")
