import asyncio
from datetime import timedelta
from uuid import UUID

import structlog
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.audit import record_audit_event
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException

logger = structlog.get_logger("titanrag.s3")

import urllib3

_minio_client: Minio | None = None


def get_minio_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=5.0, read=30.0),
            maxsize=50,
            retries=urllib3.Retry(total=3, backoff_factor=0.2),
        )
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_USE_SSL,
            http_client=http_client,
        )
    return _minio_client


async def check_minio_health() -> bool:
    try:
        client = get_minio_client()
        await asyncio.to_thread(client.list_buckets)
        return True
    except Exception as e:
        logger.warning("minio_health_check_failed", error=str(e))
        return False


def build_scoped_storage_path(
    tenant_id: UUID,
    workspace_id: UUID,
    document_id: UUID,
    filename: str,
) -> str:
    """Enforces strict multi-tenant directory scoping in MinIO."""
    clean_filename = filename.replace("/", "_")
    return f"{tenant_id}/{workspace_id}/{document_id}/{clean_filename}"


async def generate_presigned_get_url(
    tenant_id: UUID,
    workspace_id: UUID,
    document_id: UUID,
    filename: str,
    user_role: str = "MEMBER",
    expires: timedelta = timedelta(minutes=15),
    user_id: UUID | None = None,
    action: str = "download",
    db: AsyncSession | None = None,
    ip_address: str | None = None,
) -> str:
    """
    Generate a 15-minute presigned GET URL after verifying role.
    If user_role is VIEWER, raw downloads are prohibited (routed to PDF viewer).
    Records audit trail entry when db session is supplied.
    """
    is_pdf = filename.lower().endswith(".pdf")
    if user_role.upper() == "VIEWER":
        if not is_pdf:
            raise AppException(
                message="Viewers are restricted from downloading raw non-visual assets.",
                status_code=403,
                error_code="VIEWER_RESTRICTION",
            )
        if action.lower() == "download":
            raise AppException(
                message="Viewers are prohibited from downloading raw documents. Use view-url instead.",
                status_code=403,
                error_code="VIEWER_DOWNLOAD_RESTRICTED",
            )

    object_name = build_scoped_storage_path(tenant_id, workspace_id, document_id, filename)
    client = get_minio_client()

    extra_query_params: dict[str, str | list[str] | tuple[str]] = {}
    if action.lower() == "view":
        extra_query_params["response-content-disposition"] = "inline"

    try:
        url = await asyncio.to_thread(
            client.presigned_get_object,
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            expires=expires,
            extra_query_params=extra_query_params or None,
        )

        # Audit logging (Task 2.8.3)
        if db and user_id:
            audit_action_name = "DOCUMENT_VIEW" if action.lower() == "view" else "DOCUMENT_DOWNLOAD"
            await record_audit_event(
                session=db,
                tenant_id=tenant_id,
                user_id=user_id,
                action=audit_action_name,
                resource_type="document",
                resource_id=str(document_id),
                details={
                    "filename": filename,
                    "role": user_role,
                    "expires_seconds": int(expires.total_seconds()),
                },
                ip_address=ip_address,
            )

        return url
    except AppException:
        raise
    except Exception as e:
        logger.error("presigned_url_generation_failed", object_name=object_name, error=str(e))
        raise AppException(message=f"Failed to generate presigned URL: {e}", status_code=500) from e
