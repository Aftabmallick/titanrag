from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserProfileResponse,
)
from titan_backend.core.brute_force import (
    check_account_locked,
    clear_login_failures,
    raise_if_locked,
    record_login_failure,
)
from titan_backend.core.config import settings
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import AppException
from titan_backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from titan_backend.core.token_blacklist import revoke_token
from titan_backend.db.models.acl import ACLGroup
from titan_backend.db.models.tenants import Tenant
from titan_backend.db.models.users import User
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # Check existing user
    stmt = select(User).where(User.email == req.email.lower().strip())
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise AppException(
            message="User with this email already exists",
            status_code=400,
            error_code="EMAIL_ALREADY_EXISTS",
        )

    # 1. Create Tenant
    tenant_name = req.tenant_name or f"{req.email.split('@')[0]}'s Org"
    tenant = Tenant(id=uuid4(), name=tenant_name, plan="free")
    db.add(tenant)
    await db.flush()

    # 2. Create User as OWNER
    hashed_pw = get_password_hash(req.password)
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email=req.email.lower().strip(),
        hashed_password=hashed_pw,
        full_name=req.full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # 3. Create Default Workspace
    workspace = Workspace(
        id=uuid4(),
        tenant_id=tenant.id,
        name="Default Workspace",
        description="Auto-generated default workspace",
    )
    db.add(workspace)
    await db.flush()

    # 4. Add User as Owner in Workspace
    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
    )
    db.add(membership)

    # 5. Create default all-members ACL group
    acl_group = ACLGroup(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        name="all-members",
        description="Default group containing all workspace members",
        is_default=True,
    )
    db.add(acl_group)

    await db.commit()

    # Generate tokens
    access_token, _ = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        role="OWNER",
    )
    refresh_token, _ = create_refresh_token(user_id=user.id, tenant_id=tenant.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    email = req.email.strip().lower()

    # 1. Check brute force lockout
    is_locked, retry_after = await check_account_locked(email)
    if is_locked:
        response.headers["Retry-After"] = str(retry_after)
        raise_if_locked(is_locked, retry_after)

    # 2. Lookup user
    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        _, locked_now, after_secs = await record_login_failure(email)
        if locked_now:
            response.headers["Retry-After"] = str(after_secs)
            raise_if_locked(True, after_secs)

        raise AppException(
            message="Invalid email or password",
            status_code=401,
            error_code="INVALID_CREDENTIALS",
        )

    if not user.is_active:
        raise AppException(
            message="User account is deactivated",
            status_code=403,
            error_code="ACCOUNT_DEACTIVATED",
        )

    # Clear brute-force attempts on success
    await clear_login_failures(email)

    # Generate token pair
    access_token, _ = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role="ADMIN" if user.is_superuser else "MEMBER",
    )
    refresh_token, _ = create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(req: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise AppException(
            message="Invalid token type: expected refresh token",
            status_code=400,
            error_code="INVALID_TOKEN_TYPE",
        )

    old_jti = payload.get("jti")
    exp = payload.get("exp", 0)

    # Revoke old refresh token (Single-use rotation)
    if old_jti:
        await revoke_token(old_jti, exp)

    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]

    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True))
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise AppException(
            message="User not found or inactive",
            status_code=401,
            error_code="USER_NOT_FOUND",
        )

    new_access, _ = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
    )
    new_refresh, _ = create_refresh_token(user_id=user.id, tenant_id=user.tenant_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    authorization: str | None = Header(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            exp = payload.get("exp", 0)
            if jti:
                await revoke_token(jti, exp)
        except Exception:
            pass

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    stmt = select(User).where(User.id == current_user.id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise AppException(
            message="User profile not found",
            status_code=404,
            error_code="NOT_FOUND",
        )
    return UserProfileResponse.model_validate(user)


@router.post("/onboarding/complete")
async def complete_onboarding(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    stmt = select(User).where(User.id == current_user.id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        user.onboarding_completed = True
        await db.commit()
    return {"status": "ok"}
