from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.api_keys import APIKeyResponse, CreateAPIKeyRequest
from titan_backend.core.audit import audit_action
from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.core.errors import AppException
from titan_backend.core.security import generate_secure_api_key
from titan_backend.db.models.api_keys import APIKey
from titan_backend.db.session import get_db

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
@audit_action("API_KEY_CREATE", "api_key")
async def create_api_key(
    req: CreateAPIKeyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    # Validate scopes
    valid_scopes = {"read", "write", "admin"}
    for s in req.scopes:
        if s not in valid_scopes:
            raise AppException(message=f"Invalid scope: '{s}'", status_code=400)

    # Generate key
    raw_key, prefix, hashed = generate_secure_api_key(prefix="rg_live")

    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=req.expires_in_days)

    api_key_obj = APIKey(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=req.name,
        key_prefix=prefix,
        hashed_key=hashed,
        scopes=req.scopes,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(api_key_obj)
    await db.commit()
    await db.refresh(api_key_obj)

    resp = APIKeyResponse.model_validate(api_key_obj)
    resp.raw_key = raw_key
    return resp


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
    stmt = (
        select(APIKey)
        .where(
            APIKey.tenant_id == current_user.tenant_id,
            APIKey.is_revoked.is_(False),
        )
        .order_by(APIKey.created_at.desc())
    )
    res = await db.execute(stmt)
    keys = res.scalars().all()
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
@audit_action("API_KEY_REVOKE", "api_key")
async def revoke_api_key(
    key_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    stmt = select(APIKey).where(
        APIKey.id == key_id,
        APIKey.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    api_key_obj = res.scalar_one_or_none()
    if not api_key_obj:
        raise AppException(message="API key not found", status_code=404)

    api_key_obj.is_revoked = True
    await db.commit()
    return {"message": "API key successfully revoked"}
