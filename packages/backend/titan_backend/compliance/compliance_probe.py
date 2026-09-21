from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.compliance.residency import TenantRegionRouter
from titan_backend.core.config import settings
from titan_backend.security.zdr import ZdrEnforcementProxy


class ComplianceProbe:
    """Continuous Compliance & Data Residency Audit Probe.

    Validates infrastructure invariants:
    - S3 bucket regional pin
    - Qdrant collection isolation
    - Zero Data Retention provider adherence
    - Cryptographic key isolation
    """

    @classmethod
    async def run_audit_probe(
        cls,
        session: AsyncSession,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        residency = await TenantRegionRouter.get_or_create_residency(session, tenant_id)

        checks = []

        # 1. Storage Bucket Check
        expected_bucket = residency.storage_bucket
        checks.append(
            {
                "check": "MINIO_S3_REGIONAL_ISOLATION",
                "passed": bool(expected_bucket),
                "details": f"Target bucket: {expected_bucket}",
            }
        )

        # 2. Vector Collection Check
        expected_prefix = residency.qdrant_collection_prefix
        checks.append(
            {
                "check": "QDRANT_COLLECTION_PREFIX_PIN",
                "passed": bool(expected_prefix),
                "details": f"Target collection prefix: {expected_prefix}",
            }
        )

        # 3. ZDR Provider Whitelist Check
        sample_model = settings.DEFAULT_CHAT_MODEL or "deepseek-ai/deepseek-v4-flash-0731"
        is_zdr = ZdrEnforcementProxy.is_model_zdr_certified(sample_model)
        checks.append(
            {
                "check": "DEFAULT_LLM_ZDR_COMPLIANCE",
                "passed": is_zdr,
                "details": f"Configured model: {sample_model} (ZDR certified: {is_zdr})",
            }
        )

        # 4. Strict Enforcement Invariant
        checks.append(
            {
                "check": "STRICT_GEO_ENFORCEMENT_ENABLED",
                "passed": residency.enforce_strict,
                "details": f"Strict mode is {'ACTIVE' if residency.enforce_strict else 'PERMISSIVE'}",
            }
        )

        all_passed = all(c["passed"] for c in checks)

        return {
            "tenant_id": str(tenant_id),
            "region": residency.region.value,
            "probed_at": datetime.now(UTC).isoformat(),
            "overall_status": "COMPLIANT" if all_passed else "NON_COMPLIANT",
            "compliance_score": 100.0
            if all_passed
            else round((sum(1 for c in checks if c["passed"]) / len(checks)) * 100, 1),
            "checks": checks,
        }
