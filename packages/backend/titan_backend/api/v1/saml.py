from datetime import datetime, timezone
from typing import Any
import uuid
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.auth.saml import SAMLServiceProvider
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.config import settings
from titan_backend.core.dependencies import CurrentUser, get_current_user, get_db, require_admin
from titan_backend.core.security import create_access_token, create_refresh_token
from titan_backend.db.models.saml import SAMLConfiguration
from titan_backend.db.models.users import User

router = APIRouter(tags=["sso-saml"])


class SAMLConfigureRequest(BaseModel):
    idp_entity_id: str = Field(..., min_length=1, max_length=512)
    idp_sso_url: str = Field(..., min_length=1, max_length=1024)
    idp_x509_cert: str = Field(..., min_length=20)
    sp_entity_id: str | None = Field(None)
    sp_acs_url: str | None = Field(None)
    attribute_mapping: dict[str, Any] = Field(
        default_factory=lambda: {
            "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "groups": "http://schemas.xmlsoap.org/claims/Group",
        }
    )
    allow_unencrypted_assertions: bool = False


class SAMLConfigResponse(BaseModel):
    id: str
    tenant_id: str
    idp_entity_id: str
    idp_sso_url: str
    sp_entity_id: str
    sp_acs_url: str
    attribute_mapping: dict[str, Any]
    is_active: bool
    last_login_at: str | None
    created_at: str


@router.get("/auth/sso/saml/{tenant_id}/metadata", response_class=Response)
async def get_saml_sp_metadata(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Download SAML 2.0 Service Provider (SP) metadata XML for IdP import."""
    stmt = select(SAMLConfiguration).where(SAMLConfiguration.tenant_id == tenant_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    base_url = str(request.base_url).rstrip("/")
    sp_entity_id = config.sp_entity_id if config else f"{base_url}/api/v1/auth/sso/saml/{tenant_id}"
    sp_acs_url = config.sp_acs_url if config else f"{base_url}/api/v1/auth/sso/saml/{tenant_id}/acs"

    xml = SAMLServiceProvider.generate_sp_metadata(sp_entity_id, sp_acs_url)
    return Response(content=xml, media_type="application/xml")


@router.get("/auth/sso/saml/{tenant_id}/login")
async def saml_sso_login(
    tenant_id: uuid.UUID,
    relay_state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Initiate SP-initiated SAML login flow, redirecting to the IdP."""
    stmt = select(SAMLConfiguration).where(
        SAMLConfiguration.tenant_id == tenant_id,
        SAMLConfiguration.is_active.is_(True),
    )
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SAML SSO is not configured or active for this organization",
        )

    redirect_url, _ = SAMLServiceProvider.build_authn_request(config, relay_state=relay_state)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.post("/auth/sso/saml/{tenant_id}/acs")
async def saml_assertion_consumer_service(
    tenant_id: uuid.UUID,
    SAMLResponse: str = Form(...),
    RelayState: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Assertion Consumer Service (ACS) endpoint.
    Receives HTTP-POST SAMLResponse from IdP, validates assertions, performs JIT provisioning,
    invalidates cached Redis ACLs, and issues authentication JWT tokens.
    """
    stmt = select(SAMLConfiguration).where(
        SAMLConfiguration.tenant_id == tenant_id,
        SAMLConfiguration.is_active.is_(True),
    )
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SAML SSO not configured")

    try:
        assertion = SAMLServiceProvider.process_saml_response(SAMLResponse, config)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"SAML validation error: {str(e)}")

    # Just-In-Time (JIT) Provisioning
    stmt_user = select(User).where(User.email == assertion.email)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()

    if not user:
        user = User(
            email=assertion.email,
            hashed_password="SAML_USER_NO_PASSWORD",
            full_name=assertion.full_name,
            is_active=True,
            is_superuser=False,
            role="MEMBER",
        )
        db.add(user)
        await db.flush()
    else:
        user.full_name = assertion.full_name

    # Invalidate cached ACL tokens in Redis
    try:
        redis = get_redis_client()
        await redis.delete(f"user_acl:{user.id}")
    except Exception:
        pass

    # Update config last login
    config.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Issue tokens
    access_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(tenant_id),
        claims={"email": user.email, "role": user.role, "saml_groups": assertion.groups},
    )
    refresh_token = create_refresh_token(subject=str(user.id), tenant_id=str(tenant_id))

    # If RelayState is a URL, redirect with tokens in hash fragment
    if RelayState and (RelayState.startswith("http://") or RelayState.startswith("https://") or RelayState.startswith("/")):
        sep = "&" if "?" in RelayState else "?"
        dest = f"{RelayState}{sep}access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=dest, status_code=status.HTTP_302_FOUND)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "groups": assertion.groups,
        },
    }


# Admin Management Endpoints
@router.post("/admin/sso/saml", response_model=SAMLConfigResponse)
async def configure_saml(
    payload: SAMLConfigureRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin endpoint to create or update SAML IdP configuration for the tenant."""
    base_url = str(request.base_url).rstrip("/")
    sp_entity_id = payload.sp_entity_id or f"{base_url}/api/v1/auth/sso/saml/{current_user.tenant_id}"
    sp_acs_url = payload.sp_acs_url or f"{base_url}/api/v1/auth/sso/saml/{current_user.tenant_id}/acs"

    stmt = select(SAMLConfiguration).where(SAMLConfiguration.tenant_id == current_user.tenant_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    if config:
        config.idp_entity_id = payload.idp_entity_id
        config.idp_sso_url = payload.idp_sso_url
        config.idp_x509_cert = payload.idp_x509_cert
        config.sp_entity_id = sp_entity_id
        config.sp_acs_url = sp_acs_url
        config.attribute_mapping = payload.attribute_mapping
        config.allow_unencrypted_assertions = payload.allow_unencrypted_assertions
        config.is_active = True
    else:
        config = SAMLConfiguration(
            tenant_id=current_user.tenant_id,
            idp_entity_id=payload.idp_entity_id,
            idp_sso_url=payload.idp_sso_url,
            idp_x509_cert=payload.idp_x509_cert,
            sp_entity_id=sp_entity_id,
            sp_acs_url=sp_acs_url,
            attribute_mapping=payload.attribute_mapping,
            allow_unencrypted_assertions=payload.allow_unencrypted_assertions,
            is_active=True,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    return SAMLConfigResponse(
        id=str(config.id),
        tenant_id=str(config.tenant_id),
        idp_entity_id=config.idp_entity_id,
        idp_sso_url=config.idp_sso_url,
        sp_entity_id=config.sp_entity_id,
        sp_acs_url=config.sp_acs_url,
        attribute_mapping=config.attribute_mapping,
        is_active=config.is_active,
        last_login_at=config.last_login_at.isoformat() if config.last_login_at else None,
        created_at=config.created_at.isoformat(),
    )


@router.get("/admin/sso/saml", response_model=SAMLConfigResponse)
async def get_saml_config(
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SAMLConfiguration).where(SAMLConfiguration.tenant_id == current_user.tenant_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SAML configuration found")

    return SAMLConfigResponse(
        id=str(config.id),
        tenant_id=str(config.tenant_id),
        idp_entity_id=config.idp_entity_id,
        idp_sso_url=config.idp_sso_url,
        sp_entity_id=config.sp_entity_id,
        sp_acs_url=config.sp_acs_url,
        attribute_mapping=config.attribute_mapping,
        is_active=config.is_active,
        last_login_at=config.last_login_at.isoformat() if config.last_login_at else None,
        created_at=config.created_at.isoformat(),
    )
