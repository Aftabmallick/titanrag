import secrets
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.auth import TokenResponse
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException
from titan_backend.core.oauth.base import OAuthProvider
from titan_backend.core.oauth.providers import GitHubOAuthProvider, GoogleOAuthProvider
from titan_backend.core.security import create_access_token, create_refresh_token
from titan_backend.db.models.acl import ACLGroup
from titan_backend.db.models.tenants import Tenant
from titan_backend.db.models.users import User
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.db.session import get_db

router = APIRouter(prefix="/auth/oauth", tags=["OAuth2"])

STATE_PREFIX = "oauth_state:"


def _get_provider(provider: str, redirect_uri: str) -> OAuthProvider:
    if provider.lower() == "google":
        return GoogleOAuthProvider(redirect_uri=redirect_uri)
    elif provider.lower() == "github":
        return GitHubOAuthProvider(redirect_uri=redirect_uri)
    raise AppException(
        message=f"Unsupported OAuth provider: '{provider}'",
        status_code=400,
        error_code="UNSUPPORTED_PROVIDER",
    )


@router.get("/{provider}/url")
async def get_oauth_url(
    provider: str,
    request: Request,
    redirect_uri: str = Query(..., description="Callback redirect URL"),
) -> dict[str, str]:
    state = secrets.token_urlsafe(32)
    redis = await get_redis_client()
    # Store state for 5 minutes
    await redis.set(f"{STATE_PREFIX}{state}", provider.lower(), ex=300)

    oauth_prov = _get_provider(provider, redirect_uri=redirect_uri)
    auth_url = oauth_prov.get_authorization_url(state=state)
    return {"url": auth_url, "state": state}


@router.get("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(..., description="Must match the redirect_uri used in /url"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 1. Verify state in Redis
    redis = await get_redis_client()
    stored_provider: Any = await redis.get(f"{STATE_PREFIX}{state}")
    if not stored_provider or stored_provider != provider.lower():
        raise AppException(
            message="Invalid or expired OAuth state parameter (CSRF detected)",
            status_code=400,
            error_code="INVALID_OAUTH_STATE",
        )
    await redis.delete(f"{STATE_PREFIX}{state}")

    # 2. Exchange code for tokens & profile
    oauth_prov = _get_provider(provider, redirect_uri=redirect_uri)
    token_data = await oauth_prov.exchange_code(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise AppException(message="OAuth exchange did not yield an access_token", status_code=400)

    user_info = await oauth_prov.get_user_info(access_token)

    # 3. Lookup user by email or (oauth_provider, oauth_id)
    stmt = select(User).where(
        (User.email == user_info.email.lower().strip())
        | ((User.oauth_provider == user_info.provider_name) & (User.oauth_id == user_info.provider_id))
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        # First-login auto-provisioning
        tenant_name = f"{user_info.full_name or user_info.email}'s Org"
        tenant = Tenant(id=uuid4(), name=tenant_name, plan="free")
        db.add(tenant)
        await db.flush()

        user = User(
            id=uuid4(),
            tenant_id=tenant.id,
            email=user_info.email.lower().strip(),
            full_name=user_info.full_name,
            oauth_provider=user_info.provider_name,
            oauth_id=user_info.provider_id,
            is_active=True,
        )
        db.add(user)
        await db.flush()

        workspace = Workspace(
            id=uuid4(),
            tenant_id=tenant.id,
            name="Default Workspace",
            description="Auto-generated default workspace",
        )
        db.add(workspace)
        await db.flush()

        membership = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
        db.add(membership)

        acl_group = ACLGroup(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            name="all-members",
            is_default=True,
        )
        db.add(acl_group)
        await db.commit()
    else:
        # Link OAuth provider if not already linked
        if not user.oauth_provider:
            user.oauth_provider = user_info.provider_name
            user.oauth_id = user_info.provider_id
            await db.commit()

    # Generate tokens
    jwt_access, _ = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    jwt_refresh, _ = create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)

    return TokenResponse(
        access_token=jwt_access,
        refresh_token=jwt_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
