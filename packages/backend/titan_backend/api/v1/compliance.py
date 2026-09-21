from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.compliance.consent import ConsentManager
from titan_backend.compliance.export import GDPRExportService
from titan_backend.compliance.gdpr import GDPRDeletionManager
from titan_backend.compliance.ropa import RoPAService
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.db.models.compliance import (
    ConsentPurpose,
    ConsentStatus,
    GDPRDeletionRequest,
)
from titan_backend.db.session import get_db

router = APIRouter(prefix="/compliance", tags=["Compliance & Privacy"])


class InitiateDeletionRequest(BaseModel):
    user_id: UUID = Field(..., description="Target user ID to be wiped")


class ConsentPayload(BaseModel):
    purpose: ConsentPurpose
    status: ConsentStatus = ConsentStatus.GRANTED
    version: str = "v1.0"


@router.post("/gdpr/delete", summary="Initiate GDPR Right-to-Deletion Cascade")
async def initiate_gdpr_deletion(
    payload: InitiateDeletionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Users can request their own deletion; admins can request for any user in the tenant
    target_user_id = payload.user_id
    if current_user.role != "OWNER" and current_user.role != "ADMIN" and current_user.id != target_user_id:
        from titan_backend.core.errors import ForbiddenError

        raise ForbiddenError("Only admins or the user themselves can request deletion")

    req = await GDPRDeletionManager.initiate_deletion(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=target_user_id,
        requested_by_id=current_user.id,
    )
    return {
        "request_id": str(req.id),
        "user_id": str(req.user_id),
        "status": req.status.value,
        "sla_deadline": req.sla_deadline.isoformat(),
        "message": "GDPR right-to-deletion registered. Data wipe scheduled within 72-hour regulatory SLA window.",
    }


@router.post("/gdpr/requests/{request_id}/execute", summary="Execute GDPR Cascade Deletion")
async def execute_gdpr_deletion(
    request_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if current_user.role not in ["OWNER", "ADMIN"]:
        from titan_backend.core.errors import ForbiddenError

        raise ForbiddenError("Admin privilege required to execute deletion cascade")

    req = await GDPRDeletionManager.execute_cascade_deletion(session, request_id)
    return {
        "request_id": str(req.id),
        "user_id": str(req.user_id),
        "status": req.status.value,
        "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        "verification_hash": req.verification_hash,
        "audit_trail": req.audit_trail,
    }


@router.get("/gdpr/requests", summary="List GDPR Deletion Requests")
async def list_gdpr_requests(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(GDPRDeletionRequest)
        .where(GDPRDeletionRequest.tenant_id == current_user.tenant_id)
        .order_by(GDPRDeletionRequest.created_at.desc())
    )
    requests = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "status": r.status.value,
            "sla_deadline": r.sla_deadline.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "verification_hash": r.verification_hash,
            "created_at": r.created_at.isoformat(),
        }
        for r in requests
    ]


@router.get("/gdpr/requests/{request_id}/verify", summary="Verify GDPR SLA Compliance & Certificate")
async def verify_gdpr_request(
    request_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await GDPRDeletionManager.verify_deletion_sla(session, request_id)


@router.get("/gdpr/export", summary="Download Signed GDPR Data Export Archive")
async def export_user_data(
    user_id: UUID | None = Query(None, description="Target user ID (defaults to current user)"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    target_id = user_id or current_user.id
    if target_id != current_user.id and current_user.role not in ["OWNER", "ADMIN"]:
        from titan_backend.core.errors import ForbiddenError

        raise ForbiddenError("Admin privilege required to export other users' data")

    zip_buffer = await GDPRExportService.generate_export_package(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=target_id,
    )

    filename = f"titanrag_export_{target_id.hex[:8]}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/consent", summary="Record or Update User Consent")
async def record_user_consent(
    payload: ConsentPayload,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    consent = await ConsentManager.record_consent(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        purpose=payload.purpose,
        status=payload.status,
        ip_address=client_ip,
        user_agent=user_agent,
        version=payload.version,
    )
    return {
        "id": str(consent.id),
        "purpose": consent.purpose.value,
        "status": consent.status.value,
        "version": consent.version,
        "consented_at": consent.consented_at.isoformat(),
        "revoked_at": consent.revoked_at.isoformat() if consent.revoked_at else None,
    }


@router.get("/consent", summary="Get Current User Consents")
async def get_user_consents(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    consents = await ConsentManager.get_user_consents(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    return [
        {
            "id": str(c.id),
            "purpose": c.purpose.value,
            "status": c.status.value,
            "version": c.version,
            "consented_at": c.consented_at.isoformat(),
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        }
        for c in consents
    ]


@router.get("/ropa", summary="Generate GDPR Article 30 RoPA Compliance Register")
async def get_ropa_register(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await RoPAService.generate_ropa_report(session, current_user.tenant_id)
