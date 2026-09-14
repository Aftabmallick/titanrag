from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fastapi import Depends, Header, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.errors import AppException
from titan_backend.core.rbac import Permission, check_role_permission
from titan_backend.core.security import decode_token, hash_api_key
from titan_backend.core.token_blacklist import is_token_revoked
from titan_backend.db.models.api_keys import APIKey
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember
from titan_backend.db.session import get_db, set_session_tenant_id

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: UUID
    tenant_id: UUID
    email: str
    role: str = "MEMBER"
    scopes: list[str] = field(default_factory=list)
    is_superuser: bool = False
    is_api_key: bool = False


async def get_current_user(
    request: Request,
    auth_creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    Extracts and validates credentials from Bearer JWT or X-API-Key header.
    Enforces immediate session revocation and sets RLS session state.
    """
    # 1. Try Bearer JWT
    if auth_creds and auth_creds.scheme.lower() == "bearer":
        token = auth_creds.credentials
        payload = decode_token(token)

        # Check blacklist
        jti = payload.get("jti")
        if jti and await is_token_revoked(jti):
            raise AppException(
                message="Token has been revoked",
                status_code=401,
                error_code="TOKEN_REVOKED",
            )

        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload["tenant_id"])

        # Check if user has been immediately deactivated via SCIM / Admin
        try:
            redis = await get_redis_client()
            if await redis.get(f"user_deactivated:{user_id}"):
                raise AppException(
                    message="User account has been deactivated",
                    status_code=401,
                    error_code="ACCOUNT_DEACTIVATED",
                )
        except AppException:
            raise
        except Exception:
            pass

        current_user = CurrentUser(
            id=user_id,
            tenant_id=tenant_id,
            email=payload.get("email", ""),
            role=payload.get("role", "MEMBER"),
            scopes=["*"],
            is_superuser=payload.get("is_superuser", False),
            is_api_key=False,
        )
        request.state.current_user = current_user
        request.state.tenant_id = tenant_id

        # Explicitly bind tenant_id to PostgreSQL RLS session for downstream queries
        await set_session_tenant_id(db, tenant_id)

        return current_user

    # 2. Try X-API-Key
    if x_api_key:
        hashed = hash_api_key(x_api_key)
        stmt = select(APIKey).where(APIKey.hashed_key == hashed, APIKey.is_revoked.is_(False))
        result = await db.execute(stmt)
        api_key_obj = result.scalar_one_or_none()

        if not api_key_obj:
            raise AppException(
                message="Invalid or revoked API key",
                status_code=401,
                error_code="INVALID_API_KEY",
            )

        if api_key_obj.expires_at:
            from datetime import UTC, datetime

            if api_key_obj.expires_at < datetime.now(UTC):
                raise AppException(
                    message="API key has expired",
                    status_code=401,
                    error_code="API_KEY_EXPIRED",
                )

        current_user = CurrentUser(
            id=api_key_obj.user_id,
            tenant_id=api_key_obj.tenant_id,
            email=f"apikey_{api_key_obj.name}",
            role="ADMIN" if "admin" in api_key_obj.scopes else "MEMBER",
            scopes=api_key_obj.scopes,
            is_superuser=False,
            is_api_key=True,
        )
        request.state.current_user = current_user
        request.state.tenant_id = api_key_obj.tenant_id

        # Explicitly bind tenant_id to PostgreSQL RLS session for downstream queries
        await set_session_tenant_id(db, api_key_obj.tenant_id)

        return current_user

    raise AppException(
        message="Authentication credentials required (Bearer token or X-API-Key)",
        status_code=401,
        error_code="UNAUTHORIZED",
    )


def require_permission(permission: Permission) -> Callable[..., Any]:
    """
    FastAPI dependency that verifies the user's role in the current workspace.
    Requires `workspace_id` in path or query.
    """

    async def _dependency(
        workspace_id: UUID = Path(...),
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        if current_user.is_superuser:
            return current_user

        # Fetch workspace to verify tenant and settings
        ws_stmt = select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.tenant_id == current_user.tenant_id,
            Workspace.is_archived.is_(False),
        )
        ws_res = await db.execute(ws_stmt)
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise AppException(
                message="Workspace not found or access denied",
                status_code=404,
                error_code="WORKSPACE_NOT_FOUND",
            )

        # Check membership
        mem_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        mem_res = await db.execute(mem_stmt)
        membership = mem_res.scalar_one_or_none()

        if not membership:
            raise AppException(
                message="You are not a member of this workspace",
                status_code=403,
                error_code="FORBIDDEN_WORKSPACE_ACCESS",
            )

        allowed = check_role_permission(membership.role, permission, workspace.settings)
        if not allowed:
            raise AppException(
                message=f"Insufficient permissions: '{permission.value}' required",
                status_code=403,
                error_code="PERMISSION_DENIED",
                details={"required_permission": permission.value, "role": membership.role.value},
            )

        return current_user

    return _dependency


def require_scope(required_scope: str) -> Callable[..., Any]:
    async def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if "*" in current_user.scopes or required_scope in current_user.scopes:
            return current_user
        raise AppException(
            message=f"API key missing required scope: '{required_scope}'",
            status_code=403,
            error_code="INSUFFICIENT_SCOPE",
            details={"required_scope": required_scope, "granted_scopes": current_user.scopes},
        )

    return _dependency
