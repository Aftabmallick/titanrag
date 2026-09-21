from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import BadRequestError
from titan_backend.db.models.encryption import QuarantineFileLog
from titan_backend.db.session import get_db
from titan_backend.security.file_validator import FileSecurityValidator
from titan_backend.security.scanner import ClamAVScanner

router = APIRouter(prefix="/security/files", tags=["File Security & Quarantine"])


@router.post("/scan", summary="Scan and Inspect File for Malware & Exploits")
async def scan_file_security(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    content = await file.read()

    # 1. Structural & MIME Validation
    val_res = FileSecurityValidator.validate_file_content(
        filename=file.filename or "unknown",
        data=content,
    )

    # 2. ClamAV Malware Scan
    scanner = ClamAVScanner()
    scan_res = await scanner.scan_bytes(content)

    if not scan_res.is_clean:
        # Quarantine
        import uuid

        quarantine_entry = QuarantineFileLog(
            tenant_id=current_user.tenant_id,
            workspace_id=None,
            filename=file.filename or "unknown",
            content_hash_sha256=val_res["sha256"],
            mime_type=val_res["detected_type"],
            file_size_bytes=len(content),
            threat_name=scan_res.threat_name or "MALWARE_DETECTED",
            quarantine_path=f"quarantine/{current_user.tenant_id}/{uuid.uuid4()}",
            scanner_latency_ms=scan_res.latency_ms,
            details={"engine": scan_res.engine},
        )
        session.add(quarantine_entry)
        await session.commit()

        raise BadRequestError(
            f"File upload rejected: Threat '{scan_res.threat_name}' detected. File moved to quarantine."
        )

    return {
        "filename": file.filename,
        "is_clean": True,
        "detected_type": val_res["detected_type"],
        "sha256": val_res["sha256"],
        "scanner_engine": scan_res.engine,
        "scanner_latency_ms": scan_res.latency_ms,
    }


@router.get("/quarantine", summary="List Quarantined Malicious Files")
async def list_quarantined_files(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(QuarantineFileLog)
        .where(QuarantineFileLog.tenant_id == current_user.tenant_id)
        .order_by(QuarantineFileLog.created_at.desc())
    )
    entries = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(e.id),
            "filename": e.filename,
            "threat_name": e.threat_name,
            "sha256": e.content_hash_sha256,
            "file_size_bytes": e.file_size_bytes,
            "quarantine_path": e.quarantine_path,
            "scanner_latency_ms": e.scanner_latency_ms,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]
