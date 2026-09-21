from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.db.models.compliance import DataRetentionPolicy
from titan_backend.db.models.documents import Document
from titan_backend.db.models.tenants import Tenant
from titan_backend.db.models.users import User


class RoPAService:
    """Article 30 Record of Processing Activities (RoPA) Generator.

    Dynamically compiles regulatory audit reports specifying categories of personal data,
    processing purposes, data subjects, recipients, retention schedules, and technical security measures.
    """

    @staticmethod
    async def generate_ropa_report(
        session: AsyncSession,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
        tenant_name = tenant.name if tenant else "Default Tenant"

        user_count = (
            await session.execute(select(func.count(User.id)).where(User.tenant_id == tenant_id))
        ).scalar() or 0
        doc_count = (
            await session.execute(select(func.count(Document.id)).where(Document.tenant_id == tenant_id))
        ).scalar() or 0

        # Fetch active retention policies
        policies = (
            (
                await session.execute(
                    select(DataRetentionPolicy).where(
                        DataRetentionPolicy.tenant_id == tenant_id,
                        DataRetentionPolicy.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        retention_schedule = [
            {
                "resource": p.target_resource.value,
                "ttl_days": p.ttl_days,
                "action": p.action.value,
            }
            for p in policies
        ]
        if not retention_schedule:
            retention_schedule = [
                {"resource": "CHAT_MESSAGES", "ttl_days": 365, "action": "HARD_DELETE"},
                {"resource": "SEMANTIC_CACHE", "ttl_days": 7, "action": "HARD_DELETE"},
                {"resource": "AUDIT_LOGS", "ttl_days": 2555, "action": "ARCHIVE_COLD"},
            ]

        return {
            "title": f"GDPR Article 30 Record of Processing Activities — {tenant_name}",
            "generated_at": datetime.now(UTC).isoformat(),
            "tenant_id": str(tenant_id),
            "controller": {
                "organization": tenant_name,
                "contact": "dpo@titanrag.enterprise",
                "system": "TitanRAG Multimodal Platform",
            },
            "metrics": {
                "active_users": user_count,
                "indexed_documents": doc_count,
            },
            "processing_activities": [
                {
                    "activity_name": "Document Ingestion & Parsing",
                    "purpose": "Extracting text, tables, and visual embeddings for enterprise document search",
                    "lawful_basis": "Contractual Necessity (Art. 6(1)(b))",
                    "data_categories": [
                        "Business documents",
                        "Internal reports",
                        "PII in text (auto-masked via Presidio)",
                    ],
                    "data_subjects": ["Employees", "Enterprise Users", "Contractors"],
                    "storage_locations": ["PostgreSQL 16", "MinIO S3", "Qdrant Vector DB"],
                },
                {
                    "activity_name": "Semantic Chat & RAG Generation",
                    "purpose": "Retrieving relevant context and answering employee inquiries using LLM inference",
                    "lawful_basis": "Legitimate Interests (Art. 6(1)(f))",
                    "data_categories": ["Chat prompts", "Generated answers", "Feedback ratings"],
                    "data_subjects": ["Authenticated Users"],
                    "storage_locations": ["PostgreSQL 16", "Redis 7"],
                },
                {
                    "activity_name": "Audit Logging & Access Security",
                    "purpose": "Tracking document access, role permissions, and administrative changes for security audit",
                    "lawful_basis": "Legal Obligation (Art. 6(1)(c))",
                    "data_categories": ["IP Addresses", "User IDs", "Access Timestamps", "Resource Actions"],
                    "data_subjects": ["All System Users"],
                    "storage_locations": ["PostgreSQL 16 `audit_log` with RLS"],
                },
            ],
            "retention_schedules": retention_schedule,
            "security_measures": [
                "PostgreSQL Row-Level Security (RLS) on all tenant-scoped tables",
                "Envelope encryption (AES-256-GCM) with Bring Your Own Key (BYOK)",
                "MinIO Server-Side Encryption (SSE-S3 / SSE-KMS)",
                "ClamAV real-time streaming antivirus inspection on uploads",
                "Zero Data Retention (ZDR) routing on enterprise LLM inference",
                "Automated 72-hour right-to-deletion cryptographic purge engine",
            ],
            "sub_processors": [
                {
                    "name": "Self-Hosted / Private Cloud",
                    "role": "Infrastructure (PostgreSQL, Qdrant, MinIO, Redis)",
                    "country": "Region-Pinned",
                },
                {
                    "name": "LiteLLM Proxy / Azure OpenAI / Anthropic",
                    "role": "LLM Inference (contractually bound to Zero Data Retention)",
                    "country": "Region-Pinned",
                },
            ],
        }
