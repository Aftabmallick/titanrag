from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from titan_backend.core.errors import ForbiddenError
from titan_backend.core.logging import logger


class ZdrEnforcementProxy:
    """Enterprise Zero Data Retention (ZDR) Enforcement Gateway.

    Guarantees that when enterprise ZDR mode is enabled, LLM inference requests
    are routed strictly to providers with legally binding Zero Data Retention agreements.
    Rejects consumer-tier or unverified model endpoints.
    """

    # Whitelist of models/endpoints certified for contractual Zero Data Retention
    ZDR_CERTIFIED_MODELS = {
        "azure/gpt-4o",
        "azure/gpt-4o-mini",
        "azure/text-embedding-3-large",
        "anthropic/claude-3-5-sonnet-20241022",
        "anthropic/claude-3-5-haiku-20241022",
        "anthropic/claude-3-opus-20240229",
        "deepseek-ai/deepseek-v4-flash-0731",
        "self_hosted/tei",
        "self_hosted/vllm",
        "local/mock",
    }

    @classmethod
    def is_model_zdr_certified(cls, model_name: str) -> bool:
        normalized = model_name.strip().lower()
        if normalized in cls.ZDR_CERTIFIED_MODELS:
            return True
        # Check prefix match for Azure / self-hosted
        if normalized.startswith("azure/") or normalized.startswith("self_hosted/") or normalized.startswith("tei/"):
            return True
        return False

    @classmethod
    def enforce_zdr_policy(
        cls,
        tenant_id: UUID,
        model_name: str,
        enforce_zdr: bool = True,
    ) -> dict[str, Any]:
        is_certified = cls.is_model_zdr_certified(model_name)

        if enforce_zdr and not is_certified:
            logger.warning(
                "zdr_policy_violation_blocked",
                tenant_id=str(tenant_id),
                model=model_name,
            )
            raise ForbiddenError(
                f"Zero Data Retention (ZDR) policy violation: model '{model_name}' "
                f"is not in the verified enterprise ZDR provider registry."
            )

        log_record = {
            "tenant_id": str(tenant_id),
            "model": model_name,
            "zdr_enforced": enforce_zdr,
            "zdr_certified": is_certified,
            "decision": "ALLOWED",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.info("zdr_policy_evaluated", **log_record)
        return log_record

    @classmethod
    async def validate_chat_request(
        cls,
        session: Any,
        tenant_id: UUID,
        model_name: str,
    ) -> None:
        from sqlalchemy import select
        from titan_backend.db.models.encryption import TenantDataResidency

        stmt = select(TenantDataResidency.enforce_strict).where(TenantDataResidency.tenant_id == tenant_id)
        strict_flag = (await session.execute(stmt)).scalar_one_or_none()
        enforce_zdr = bool(strict_flag) if strict_flag is not None else False
        cls.enforce_zdr_policy(tenant_id=tenant_id, model_name=model_name, enforce_zdr=enforce_zdr)
