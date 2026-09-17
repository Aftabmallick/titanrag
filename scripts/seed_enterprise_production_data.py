"""TitanRAG Enterprise Production Data Seeder.

Populates realistic, production-grade test entities into the default workspace:
- Prompt Templates with versions (v1, v2) and active deployment environments
- Golden Evaluation Datasets & baseline Evaluation Runs with RAG Triad scores
- A/B Experiments with control & treatment configurations and significance metrics
- FinOps Token Ledger records and monthly budget ceilings
- Chat Sessions, Messages, and User Feedback for the Flywheel Triage queue

Idempotent: Safe to run repeatedly.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from titan_backend.db.models.ab_testing import ABExperiment, ABExperimentStatus
from titan_backend.db.models.chat import ChatMessage, ChatSession, MessageRole
from titan_backend.db.models.evaluation import (
    EvaluationResultItem,
    EvaluationRun,
    EvaluationStatus,
    EvaluationTrigger,
    GoldenDataset,
    GoldenDatasetItem,
)
from titan_backend.db.models.feedback import Feedback, FeedbackTriageStatus
from titan_backend.db.models.finops import FinOpsLedger, FinOpsOperation
from titan_backend.db.models.promptops import PromptEnvironment, PromptTemplate, PromptVersion
from titan_backend.db.models.tenants import Tenant
from titan_backend.db.models.users import User
from titan_backend.db.models.workspaces import Workspace


def get_db_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres_dev_password@localhost:5432/titanrag")
    if "postgresql://" in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    return url


async def seed_data():
    engine = create_async_engine(get_db_url(), echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        print("🌱 Seeding Enterprise Production Data...")

        # 1. Tenant & Admin User & Workspace
        tenant_stmt = select(Tenant).order_by(Tenant.created_at).limit(1)
        tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                name="Enterprise Default",
                slug="enterprise-default",
                is_active=True,
            )
            session.add(tenant)
            await session.flush()

        tenant_id = tenant.id

        user_stmt = select(User).where(User.email == "admin@titanrag.io")
        user = (await session.execute(user_stmt)).scalar_one_or_none()
        if not user:
            from titan_backend.core.security import get_password_hash

            user = User(
                tenant_id=tenant_id,
                email="admin@titanrag.io",
                hashed_password=get_password_hash("TitanAdmin123!"),
                full_name="Titan Administrator",
                is_active=True,
                is_superuser=True,
            )
            session.add(user)
            await session.flush()

        user_id = user.id

        ws_stmt = select(Workspace).where(Workspace.tenant_id == tenant_id).order_by(Workspace.created_at).limit(1)
        workspace = (await session.execute(ws_stmt)).scalar_one_or_none()
        if not workspace:
            workspace = Workspace(
                tenant_id=tenant_id,
                name="Default Workspace",
                description="Enterprise Defense Knowledge Base",
                settings={"quota_limits": {"max_compute_units": 500.0}},
            )
            session.add(workspace)
            await session.flush()
        else:
            # Ensure monthly budget cap is set in workspace settings
            ws_settings = dict(workspace.settings or {})
            if "quota_limits" not in ws_settings:
                ws_settings["quota_limits"] = {"max_compute_units": 500.0}
                workspace.settings = ws_settings
                session.add(workspace)
                await session.flush()

        workspace_id = workspace.id
        print(f"✓ Tenant: {tenant.name} ({tenant_id})")
        print(f"✓ Workspace: {workspace.name} ({workspace_id})")
        print(f"✓ User: {user.email} ({user_id})")

        # 2. Prompt Templates & Versions
        system_chat_stmt = select(PromptTemplate).where(
            PromptTemplate.workspace_id == workspace_id,
            PromptTemplate.slug == "system_chat",
        )
        system_chat = (await session.execute(system_chat_stmt)).scalar_one_or_none()
        if not system_chat:
            system_chat = PromptTemplate(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                slug="system_chat",
                name="Core RAG System Prompt",
                description="Controls high-assurance grounded generation, strict citation attribution, and tone.",
            )
            session.add(system_chat)
            await session.flush()

            v1 = PromptVersion(
                template_id=system_chat.id,
                version_number=1,
                environment=PromptEnvironment.STAGING,
                content="You are TitanRAG, an enterprise AI assistant. Answer the user question accurately using the context provided below.\n\nContext:\n{{ context }}\n\nUser Question:\n{{ question }}",
                input_schema={"context": "string", "question": "string"},
                commit_message="Initial baseline system prompt",
                author_id=user_id,
                is_active=False,
                token_count_estimate=32,
            )
            v2 = PromptVersion(
                template_id=system_chat.id,
                version_number=2,
                environment=PromptEnvironment.PROD,
                content="You are TitanRAG, a high-assurance enterprise defense AI assistant.\nAnswer the user inquiry strictly utilizing the verified sources provided below.\n\nInvariants:\n1. Cite every claim with inline bracket markers [1], [2].\n2. If the answer is not supported by context, respond: 'I do not have sufficient grounded context.'\n\nContext:\n{{ context }}\n\nUser Question:\n{{ question }}",
                input_schema={"context": "string", "question": "string"},
                commit_message="Enforce strict bracketed citations [1] and out-of-domain rejection",
                author_id=user_id,
                is_active=True,
                token_count_estimate=48,
            )
            session.add_all([v1, v2])
            print("✓ Seeded system_chat prompt template (v1 STAGING, v2 PROD)")

        # 3. Golden Evaluation Datasets & Baseline Runs
        ds_stmt = select(GoldenDataset).where(GoldenDataset.workspace_id == workspace_id)
        dataset = (await session.execute(ds_stmt)).scalars().first()
        if not dataset:
            dataset = GoldenDataset(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                name="Enterprise Defense & Compliance Benchmark",
                description="Curated high-assurance test suite verifying SOC2, encryption standards, and retrieval SLAs.",
                version=1,
                tags=["compliance", "soc2", "sla-verification"],
                is_active=True,
            )
            session.add(dataset)
            await session.flush()

            items = [
                GoldenDatasetItem(
                    dataset_id=dataset.id,
                    query="What is the mandatory retention period for SOC 2 Type II audit logs in TitanRAG?",
                    expected_answer="Audit logs must be preserved immutably for a minimum of 7 years with SHA-256 cryptographic hashing.",
                    expected_chunk_ids=["chk-audit-sec-01", "chk-audit-sec-02"],
                    expected_document_ids=["doc-soc2-compliance"],
                    context="Section 4.2 Audit Retention: All control plane and query telemetry logs are hashed via SHA-256 and archived to immutable S3 Object Lock storage for a 7-year statutory period.",
                    tags=["compliance", "retention"],
                ),
                GoldenDatasetItem(
                    dataset_id=dataset.id,
                    query="Which encryption algorithms are enforced for data at rest and in transit?",
                    expected_answer="AES-256-GCM is enforced for data at rest, and TLS 1.3 with forward secrecy is enforced for data in transit.",
                    expected_chunk_ids=["chk-crypto-01"],
                    expected_document_ids=["doc-security-whitepaper"],
                    context="Cryptographic Specifications: TitanRAG strictly enforces AES-256-GCM authenticated encryption for all volume and vector storage. Network transit mandates TLS 1.3 with PFS.",
                    tags=["cryptography", "infosec"],
                ),
                GoldenDatasetItem(
                    dataset_id=dataset.id,
                    query="What is the maximum allowed fast-path retrieval SLA?",
                    expected_answer="Fast-path hybrid retrieval must return candidate context within 1.8 seconds (p99).",
                    expected_chunk_ids=["chk-sla-09"],
                    expected_document_ids=["doc-architecture-sla"],
                    context="Operational SLA: Fast-path direct vector query executions adhere to a sub-1.8s p99 latency threshold before falling back to multi-hop deep research.",
                    tags=["performance", "sla"],
                ),
                GoldenDatasetItem(
                    dataset_id=dataset.id,
                    query="How does the atomic Redis quota gatekeeper handle tenant budget overage?",
                    expected_answer="At 80% quota consumption a soft warning alert is broadcast, and at 100% quota consumption HTTP 429 is returned.",
                    expected_chunk_ids=["chk-finops-03"],
                    expected_document_ids=["doc-finops-spec"],
                    context="Compute Unit Enforcement: At 80% consumption, an async quota_warning webhook fires. At 100% limit, the gateway rejects invocations with HTTP 429 Quota Exceeded.",
                    tags=["finops", "rate-limiting"],
                ),
            ]
            session.add_all(items)
            await session.flush()

            # Seed Completed Benchmark Run
            eval_run = EvaluationRun(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset.id,
                status=EvaluationStatus.COMPLETED,
                triggered_by=EvaluationTrigger.MANUAL,
                rag_config_snapshot={
                    "retrieval_mode": "HYBRID",
                    "dense_weight": 0.7,
                    "sparse_weight": 0.3,
                    "top_k": 20,
                    "rerank_top_k": 5,
                },
                aggregate_scores={
                    "faithfulness": 0.94,
                    "answer_relevancy": 0.89,
                    "context_precision": 0.91,
                    "context_recall": 0.86,
                    "ndcg_at_k": 0.93,
                    "mrr": 0.95,
                    "precision_at_k": 0.92,
                    "recall_at_k": 0.88,
                },
                latency_stats={"avg_latency_ms": 1240, "p95_latency_ms": 1680},
                total_compute_units=48.2,
                total_dollar_cost=0.0482,
            )
            session.add(eval_run)
            await session.flush()

            for item in items:
                session.add(
                    EvaluationResultItem(
                        run_id=eval_run.id,
                        dataset_item_id=item.id,
                        query=item.query,
                        generated_answer=item.expected_answer,
                        retrieved_chunk_ids=item.expected_chunk_ids,
                        scores={
                            "faithfulness": 0.95,
                            "relevance": 0.90,
                            "precision": 0.92,
                        },
                        latency_ms=1250.0,
                        tokens_used=180,
                        cost_cu=0.012,
                    )
                )
            print("✓ Seeded Golden Dataset (4 items) and completed benchmark Evaluation Run")

        # 4. A/B Testing Experiment
        exp_stmt = select(ABExperiment).where(ABExperiment.workspace_id == workspace_id)
        experiment = (await session.execute(exp_stmt)).scalars().first()
        if not experiment:
            experiment = ABExperiment(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                name="Hybrid Search Alpha Optimization: 0.7 vs 0.5",
                description="Testing whether increasing lexical BM25 weight to 0.5 improves technical acronym retrieval precision.",
                status=ABExperimentStatus.RUNNING,
                traffic_split=50,
                control_config={
                    "retrieval_mode": "HYBRID",
                    "dense_weight": 0.7,
                    "sparse_weight": 0.3,
                    "top_k": 20,
                    "rerank_top_k": 5,
                },
                treatment_config={
                    "retrieval_mode": "HYBRID",
                    "dense_weight": 0.5,
                    "sparse_weight": 0.5,
                    "top_k": 25,
                    "rerank_top_k": 5,
                },
                sample_size_control=620,
                sample_size_treatment=615,
                primary_metric="SATISFACTION_RATE",
                p_value=0.038,
                statistical_significance=True,
                winning_variant="TREATMENT",
                start_time=datetime.now(UTC) - timedelta(days=7),
            )
            session.add(experiment)
            print("✓ Seeded active A/B Experiment with statistical significance metrics")

        # 5. FinOps Ledger Transactions
        ledger_count_stmt = select(FinOpsLedger).where(FinOpsLedger.workspace_id == workspace_id).limit(1)
        has_ledger = (await session.execute(ledger_count_stmt)).scalar_one_or_none()
        if not has_ledger:
            now = datetime.now(UTC)
            records = [
                FinOpsLedger(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    request_id="req-chat-prod-01",
                    operation_type=FinOpsOperation.CHAT_FAST,
                    prompt_tokens=14200,
                    completion_tokens=3400,
                    gpu_seconds=12.4,
                    compute_units=120.0,
                    dollar_cost=1.20,
                    model_name="deepseek-ai/deepseek-v4-flash-0731",
                    provider="litellm",
                    details={"cached": False, "department": "Security Architecture"},
                    created_at=now - timedelta(days=5),
                ),
                FinOpsLedger(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    request_id="req-chat-prod-02",
                    operation_type=FinOpsOperation.CHAT_DEEP,
                    prompt_tokens=28000,
                    completion_tokens=8200,
                    gpu_seconds=34.1,
                    compute_units=160.0,
                    dollar_cost=1.60,
                    model_name="gpt-4o-mini",
                    provider="openai",
                    details={"cached": False, "department": "Legal & Compliance"},
                    created_at=now - timedelta(days=3),
                ),
                FinOpsLedger(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    request_id="req-embed-01",
                    operation_type=FinOpsOperation.INGESTION_EMBEDDING,
                    prompt_tokens=45000,
                    completion_tokens=0,
                    gpu_seconds=8.2,
                    compute_units=35.0,
                    dollar_cost=0.35,
                    model_name="text-embedding-3-small",
                    provider="litellm",
                    details={"chunks": 180, "department": "Data Ingestion"},
                    created_at=now - timedelta(days=2),
                ),
                FinOpsLedger(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    request_id="req-rerank-01",
                    operation_type=FinOpsOperation.RERANK,
                    prompt_tokens=18000,
                    completion_tokens=0,
                    gpu_seconds=4.5,
                    compute_units=27.5,
                    dollar_cost=0.275,
                    model_name="bge-reranker-large",
                    provider="onnx-local",
                    details={"candidates": 20, "department": "Search Pipeline"},
                    created_at=now - timedelta(days=1),
                ),
            ]
            session.add_all(records)
            print("✓ Seeded FinOps Ledger transactions (342.5 CU total, ~68.5% utilization)")

        # 6. Chat Session, Messages & User Feedback for Triage Queue
        chat_stmt = select(ChatSession).where(ChatSession.workspace_id == workspace_id).limit(1)
        chat_sess = (await session.execute(chat_stmt)).scalar_one_or_none()
        if not chat_sess:
            chat_sess = ChatSession(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id=user_id,
                title="SOC 2 Type II SLA Invariants Review",
            )
            session.add(chat_sess)
            await session.flush()

            msg_user = ChatMessage(
                session_id=chat_sess.id,
                role=MessageRole.USER,
                content="Can you summarize the statutory audit log retention rule?",
                tokens_used=12,
            )
            msg_asst = ChatMessage(
                session_id=chat_sess.id,
                role=MessageRole.ASSISTANT,
                content="TitanRAG retains all audit telemetry logs for a period of 5 years with SHA-256 integrity checks [1].",
                tokens_used=26,
                citations=[
                    {
                        "citation_id": "c-01",
                        "document_id": str(uuid4()),
                        "chunk_id": "chk-audit-sec-01",
                        "document_name": "TitanRAG_SOC2_Compliance.pdf",
                        "page_number": 4,
                    }
                ],
            )
            session.add_all([msg_user, msg_asst])
            await session.flush()

            # Seed negative feedback on assistant message for Flywheel triage
            fb = Feedback(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                session_id=chat_sess.id,
                message_id=msg_asst.id,
                user_id=user_id,
                rating=-1,
                comment="The retention period specified in the compliance guide is 7 years, not 5 years.",
                corrected_answer="Audit logs must be preserved immutably for a minimum of 7 years with SHA-256 cryptographic hashing.",
                citation_issues=[
                    {
                        "citation_id": "c-01",
                        "issue": "Hallucinated retention metric (stated 5 years instead of 7)",
                    }
                ],
                triage_status=FeedbackTriageStatus.NEW,
            )
            # Also seed one positive feedback
            fb_pos = Feedback(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                session_id=chat_sess.id,
                message_id=msg_asst.id,
                user_id=user_id,
                rating=1,
                comment="Accurate citation reference to Section 4.2.",
                citation_issues=[],
                triage_status=FeedbackTriageStatus.TRIAGED,
            )
            session.add_all([fb, fb_pos])
            print("✓ Seeded Chat Session, Grounded Message, and User Feedback for Flywheel Triage")

        await session.commit()
        print("\n✨ Enterprise production data seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
