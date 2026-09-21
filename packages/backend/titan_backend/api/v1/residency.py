from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.compliance.compliance_probe import ComplianceProbe
from titan_backend.compliance.residency import TenantRegionRouter
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import ForbiddenError
from titan_backend.db.models.encryption import DataResidencyRegion
from titan_backend.db.session import get_db
from titan_backend.security.zdr import ZdrEnforcementProxy

router = APIRouter(prefix="/compliance/residency", tags=["Data Residency & ZDR"])


class ConfigureResidencyPayload(BaseModel):
    region: DataResidencyRegion
    enforce_strict: bool = True


class ValidateZdrPayload(BaseModel):
    model_name: str
    enforce_zdr: bool = True


@router.get("", summary="Get Current Tenant Data Residency & Region")
async def get_tenant_residency(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    residency = await TenantRegionRouter.get_or_create_residency(session, current_user.tenant_id)
    return {
        "tenant_id": str(residency.tenant_id),
        "region": residency.region.value,
        "enforce_strict": residency.enforce_strict,
        "storage_bucket": residency.storage_bucket,
        "database_schema": residency.database_schema,
        "qdrant_collection_prefix": residency.qdrant_collection_prefix,
        "created_at": residency.created_at.isoformat(),
    }


@router.post("", summary="Configure Data Residency Region")
async def update_tenant_residency(
    payload: ConfigureResidencyPayload,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role not in ["OWNER", "ADMIN"]:
        raise ForbiddenError("Admin privilege required to update data residency policies")

    residency = await TenantRegionRouter.update_residency(
        session=session,
        tenant_id=current_user.tenant_id,
        region=payload.region,
        enforce_strict=payload.enforce_strict,
    )
    return {
        "tenant_id": str(residency.tenant_id),
        "region": residency.region.value,
        "enforce_strict": residency.enforce_strict,
        "storage_bucket": residency.storage_bucket,
        "qdrant_collection_prefix": residency.qdrant_collection_prefix,
        "status": "RESIDENCY_UPDATED",
    }


@router.post("/audit-probe", summary="Run Live Data Residency Compliance Scorecard")
async def run_residency_audit(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ComplianceProbe.run_audit_probe(session, current_user.tenant_id)


@router.post("/check-zdr", summary="Verify Model Zero Data Retention (ZDR) Certification")
async def verify_model_zdr(
    payload: ValidateZdrPayload,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return ZdrEnforcementProxy.enforce_zdr_policy(
        tenant_id=current_user.tenant_id,
        model_name=payload.model_name,
        enforce_zdr=payload.enforce_zdr,
    )
