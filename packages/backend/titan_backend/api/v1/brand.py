"""White-Label Brand Configuration API — Phase 10.

Routes:
  GET  /api/v1/branding           — public brand config resolution (hostname-based)
  GET  /api/v1/admin/brand        — get brand config for current tenant
  PUT  /api/v1/admin/brand        — update brand config (admin only)
  POST /api/v1/admin/brand/assets — upload brand asset (logo/favicon) to MinIO
  POST /api/v1/admin/brand/domain/verify — trigger DNS verification check
"""

from __future__ import annotations

import hashlib
import io
import re
import secrets
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.config import settings
from titan_backend.core.dependencies import get_current_user, require_role
from titan_backend.db.deps import get_db
from titan_backend.db.models.billing import TenantBrandConfig
from titan_backend.db.models.user import User, UserRole

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["White-Label Branding"])

# Regex for hex color validation
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BrandConfigSchema(BaseModel):
    company_name: str = Field(default="TitanRAG", max_length=128)
    primary_color: str = Field(default="#6366f1")
    accent_color: str = Field(default="#8b5cf6")
    custom_domain: str | None = Field(default=None, max_length=255)
    from_email: str | None = Field(default=None, max_length=256)
    from_name: str | None = Field(default=None, max_length=128)
    # Asset URLs returned to clients (presigned at serve time)
    logo_light_url: str | None = None
    logo_dark_url: str | None = None
    favicon_url: str | None = None
    domain_verified: bool = False

    @field_validator("primary_color", "accent_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(f"Color must be a 6-digit hex code like #6366f1, got: {v!r}")
        return v.upper()


class PublicBrandConfigResponse(BaseModel):
    """Minimal brand config exposed to unauthenticated clients (Next.js middleware)."""

    company_name: str
    primary_color: str
    accent_color: str
    logo_light_url: str | None
    logo_dark_url: str | None
    favicon_url: str | None
    custom_domain: str | None


class AssetUploadResponse(BaseModel):
    asset_type: str
    object_key: str
    url: str  # presigned URL for immediate preview


class DomainVerifyResponse(BaseModel):
    verified: bool
    message: str
    verification_token: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_or_create_brand_config(db: AsyncSession, tenant_id: object) -> TenantBrandConfig:
    """Return existing brand config or create a default one."""
    result = await db.execute(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == tenant_id))
    config = result.scalar_one_or_none()
    if not config:
        config = TenantBrandConfig(tenant_id=tenant_id)
        db.add(config)
        await db.flush()
    return config


async def _presign_asset_url(object_key: str | None) -> str | None:
    """Generate a short-lived MinIO presigned URL for a brand asset."""
    if not object_key:
        return None
    try:
        from datetime import timedelta

        from titan_backend.core.minio import get_minio_client

        minio = get_minio_client()
        url = minio.presigned_get_object(
            settings.MINIO_BUCKET,
            object_key,
            expires=timedelta(hours=1),
        )
        return str(url)
    except Exception as exc:
        logger.warning("brand_asset_presign_failed", key=object_key, error=str(exc))
        return None


async def _brand_config_to_schema(config: TenantBrandConfig) -> BrandConfigSchema:
    return BrandConfigSchema(
        company_name=config.company_name,
        primary_color=config.primary_color,
        accent_color=config.accent_color,
        custom_domain=config.custom_domain,
        from_email=config.from_email,
        from_name=config.from_name,
        logo_light_url=await _presign_asset_url(config.logo_light_key),
        logo_dark_url=await _presign_asset_url(config.logo_dark_key),
        favicon_url=await _presign_asset_url(config.favicon_key),
        domain_verified=config.domain_verified,
    )


def _invalidate_brand_cache(tenant_id: str) -> None:
    """Invalidate Redis cache for brand config (fire-and-forget)."""
    try:
        from titan_backend.core.redis import get_redis_client_sync

        redis = get_redis_client_sync()
        redis.delete(f"brand_config:{tenant_id}")
    except Exception:
        pass  # Cache invalidation is best-effort


# ---------------------------------------------------------------------------
# Public endpoint — called by Next.js middleware & embeddable widget
# ---------------------------------------------------------------------------


@router.get("/branding", response_model=PublicBrandConfigResponse)
async def get_public_brand_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PublicBrandConfigResponse:
    """Resolve brand config for a hostname or authenticated tenant.

    Used by:
    - Next.js middleware (injects CSS vars for every page)
    - Embeddable widget (applies branding from api-key's tenant)
    - Custom domain routing (host header → tenant lookup)

    Cached in Redis for 5 minutes. Cache-busted on PUT /admin/brand.
    """
    import json

    from titan_backend.core.redis import get_redis_client

    # Try to resolve tenant from Authorization header if present
    tenant_id: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from titan_backend.api.v1.auth import decode_access_token

            payload = decode_access_token(auth_header[7:])
            tenant_id = payload.get("tenant_id")
        except Exception:
            pass

    # Fall back to hostname-based resolution
    if not tenant_id:
        host = request.headers.get("host", "").split(":")[0]
        if host and host not in ("localhost", "127.0.0.1", "0.0.0.0", "testserver") and not host.endswith(".localhost"):
            domain_result = await db.execute(
                select(TenantBrandConfig).where(
                    TenantBrandConfig.custom_domain == host,
                    TenantBrandConfig.domain_verified == True,  # noqa: E712
                )
            )
            domain_config = domain_result.scalar_one_or_none()
            if domain_config:
                tenant_id = str(domain_config.tenant_id)

    if not tenant_id:
        # No tenant resolved — return default platform brand
        return PublicBrandConfigResponse(
            company_name="TitanRAG",
            primary_color="#6366f1",
            accent_color="#8b5cf6",
            logo_light_url=None,
            logo_dark_url=None,
            favicon_url=None,
            custom_domain=None,
        )

    # Check Redis cache
    redis = await get_redis_client()
    cache_key = f"brand_config:{tenant_id}"
    cached = await redis.get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            return PublicBrandConfigResponse(**data)
        except Exception:
            pass

    # DB lookup
    result = await db.execute(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == tenant_id))
    config = result.scalar_one_or_none()
    if not config:
        return PublicBrandConfigResponse(
            company_name="TitanRAG",
            primary_color="#6366f1",
            accent_color="#8b5cf6",
            logo_light_url=None,
            logo_dark_url=None,
            favicon_url=None,
            custom_domain=None,
        )

    response = PublicBrandConfigResponse(
        company_name=config.company_name,
        primary_color=config.primary_color,
        accent_color=config.accent_color,
        logo_light_url=await _presign_asset_url(config.logo_light_key),
        logo_dark_url=await _presign_asset_url(config.logo_dark_key),
        favicon_url=await _presign_asset_url(config.favicon_key),
        custom_domain=config.custom_domain if config.domain_verified else None,
    )

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, response.model_dump_json())
    return response


# ---------------------------------------------------------------------------
# Admin endpoints — require ADMIN or OWNER role
# ---------------------------------------------------------------------------


@router.get("/admin/brand", response_model=BrandConfigSchema)
async def get_brand_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BrandConfigSchema:
    """Retrieve the current tenant's brand configuration."""
    config = await _get_or_create_brand_config(db, current_user.tenant_id)
    return await _brand_config_to_schema(config)


@router.put("/admin/brand", response_model=BrandConfigSchema)
async def update_brand_config(
    body: BrandConfigSchema,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> BrandConfigSchema:
    """Update brand configuration. Requires ADMIN or OWNER role.

    Custom domain changes reset domain_verified to False and generate
    a new DNS TXT verification token.
    """
    config = await _get_or_create_brand_config(db, current_user.tenant_id)

    config.company_name = body.company_name
    config.primary_color = body.primary_color
    config.accent_color = body.accent_color
    config.from_email = body.from_email
    config.from_name = body.from_name

    # Custom domain change → reset verification
    if body.custom_domain != config.custom_domain:
        config.custom_domain = body.custom_domain
        config.domain_verified = False
        config.domain_verification_token = secrets.token_hex(16) if body.custom_domain else None

    await db.flush()

    # Invalidate Redis cache
    _invalidate_brand_cache(str(current_user.tenant_id))

    logger.info(
        "brand_config_updated",
        tenant_id=str(current_user.tenant_id),
        company_name=body.company_name,
    )
    return await _brand_config_to_schema(config)


@router.post("/admin/brand/assets", response_model=AssetUploadResponse)
async def upload_brand_asset(
    asset_type: str,  # "logo_light" | "logo_dark" | "favicon"
    file: Annotated[UploadFile, File(...)],
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AssetUploadResponse:
    """Upload a brand asset (logo or favicon) to MinIO.

    Validates: image MIME type, max 2MB, square-ish dimensions.
    Returns presigned URL for immediate preview.
    """
    if asset_type not in ("logo_light", "logo_dark", "favicon"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_ASSET_TYPE",
                "message": "asset_type must be logo_light, logo_dark, or favicon",
            },
        )

    # Validate MIME type
    allowed_types = {"image/png", "image/jpeg", "image/svg+xml", "image/webp", "image/x-icon"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": f"Allowed image types: {', '.join(allowed_types)}",
            },
        )

    content = await file.read()

    # Max 2MB
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "FILE_TOO_LARGE", "message": "Brand assets must be ≤ 2MB"},
        )

    tenant_id = str(current_user.tenant_id)
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    ext = (file.filename or "asset.png").rsplit(".", 1)[-1].lower()
    object_key = f"_platform/{tenant_id}/brand/{asset_type}_{content_hash}.{ext}"

    try:
        from titan_backend.core.minio import get_minio_client

        minio = get_minio_client()
        minio.put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_key,
            data=io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as exc:
        logger.error("brand_asset_upload_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "UPLOAD_FAILED", "message": "Failed to upload asset to storage"},
        ) from exc

    # Update brand config with new key
    config = await _get_or_create_brand_config(db, current_user.tenant_id)
    field_map = {
        "logo_light": "logo_light_key",
        "logo_dark": "logo_dark_key",
        "favicon": "favicon_key",
    }
    setattr(config, field_map[asset_type], object_key)
    await db.flush()
    _invalidate_brand_cache(tenant_id)

    presigned_url = await _presign_asset_url(object_key) or ""
    return AssetUploadResponse(
        asset_type=asset_type,
        object_key=object_key,
        url=presigned_url,
    )


@router.post("/admin/brand/domain/verify", response_model=DomainVerifyResponse)
async def verify_custom_domain(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DomainVerifyResponse:
    """Check DNS TXT record for custom domain verification.

    Tenant must create a TXT record:
      _titanrag-verify.{custom_domain} → {verification_token}

    Returns verified=True and sets domain_verified=True in DB on success.
    """
    config = await _get_or_create_brand_config(db, current_user.tenant_id)
    if not config.custom_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_CUSTOM_DOMAIN", "message": "No custom domain configured"},
        )
    if not config.domain_verification_token:
        config.domain_verification_token = secrets.token_hex(16)
        await db.flush()

    # DNS TXT lookup

    try:
        import dns.resolver  # type: ignore[import-untyped]

        txt_name = f"_titanrag-verify.{config.custom_domain}"
        answers = dns.resolver.resolve(txt_name, "TXT")
        txt_values = [str(r).strip('"') for r in answers]
        verified = config.domain_verification_token in txt_values
    except Exception:
        verified = False

    if verified:
        config.domain_verified = True
        await db.flush()
        _invalidate_brand_cache(str(current_user.tenant_id))
        logger.info(
            "custom_domain_verified",
            tenant_id=str(current_user.tenant_id),
            domain=config.custom_domain,
        )
        return DomainVerifyResponse(
            verified=True,
            message=f"Domain {config.custom_domain} verified successfully",
            verification_token=None,
        )
    else:
        return DomainVerifyResponse(
            verified=False,
            message=(
                f"DNS TXT record not found. Add TXT record: "
                f"_titanrag-verify.{config.custom_domain} = {config.domain_verification_token}"
            ),
            verification_token=config.domain_verification_token,
        )
