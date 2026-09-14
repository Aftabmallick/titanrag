import json
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.schemas.acl import (
    ACLGroupMemberResponse,
    ACLGroupResponse,
    AddGroupMemberRequest,
    CreateACLGroupRequest,
    UpdateACLGroupRequest,
)
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.audit import audit_action
from titan_backend.core.dependencies import CurrentUser, require_permission
from titan_backend.core.errors import AppException
from titan_backend.core.rbac import Permission
from titan_backend.db.models.acl import ACLGroup, ACLGroupMember
from titan_backend.db.models.users import User
from titan_backend.db.session import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}/acl-groups", tags=["ACL Groups"])


async def invalidate_user_acl_cache(user_id: UUID) -> None:
    """
    Safely invalidates cached ACL keys using non-blocking SCAN instead of KEYS *.
    """
    try:
        redis = await get_redis_client()
        keys_to_delete = []
        async for key in redis.scan_iter(match=f"user_acl:{user_id}:*", count=100):
            keys_to_delete.append(key)
        if keys_to_delete:
            await redis.delete(*keys_to_delete)
    except Exception:
        pass


async def resolve_user_acl_groups(
    user_id: UUID,
    workspace_id: UUID,
    db: AsyncSession,
) -> list[str]:
    """
    Dynamically resolves user's effective ACL group IDs with Redis caching
    and compacted key limit (<= 50 discrete keys) for Qdrant filters.
    """
    cache_key = f"user_acl:{user_id}:{workspace_id}"
    try:
        redis = await get_redis_client()
        cached = await redis.get(cache_key)
        if cached:
            return cast(list[str], json.loads(cached))
    except Exception:
        pass

    # Query groups from database
    stmt = (
        select(ACLGroup.id)
        .join(ACLGroupMember, ACLGroup.id == ACLGroupMember.group_id)
        .where(
            ACLGroup.workspace_id == workspace_id,
            ACLGroupMember.user_id == user_id,
        )
    )
    res = await db.execute(stmt)
    group_ids = [str(gid) for gid in res.scalars().all()]

    # Also include default 'all-members' group
    default_stmt = select(ACLGroup.id).where(
        ACLGroup.workspace_id == workspace_id,
        ACLGroup.is_default.is_(True),
    )
    def_res = await db.execute(default_stmt)
    def_gid = def_res.scalar_one_or_none()
    if def_gid and str(def_gid) not in group_ids:
        group_ids.append(str(def_gid))

    # Capped at <= 50 keys to preserve HNSW graph performance
    compacted = group_ids[:50]

    try:
        redis = await get_redis_client()
        await redis.set(cache_key, json.dumps(compacted), ex=300)  # 5min TTL
    except Exception:
        pass

    return compacted


@router.post("", response_model=ACLGroupResponse, status_code=status.HTTP_201_CREATED)
@audit_action("ACL_GROUP_CREATE", "acl_group")
async def create_acl_group(
    workspace_id: UUID,
    req: CreateACLGroupRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_ACL)),
    db: AsyncSession = Depends(get_db),
) -> ACLGroupResponse:
    group = ACLGroup(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        name=req.name,
        description=req.description,
        is_default=False,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return ACLGroupResponse.model_validate(group)


@router.get("", response_model=list[ACLGroupResponse])
async def list_acl_groups(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
    db: AsyncSession = Depends(get_db),
) -> list[ACLGroupResponse]:
    stmt = (
        select(ACLGroup, func.count(ACLGroupMember.id).label("member_count"))
        .outerjoin(ACLGroupMember, ACLGroup.id == ACLGroupMember.group_id)
        .where(
            ACLGroup.workspace_id == workspace_id,
            ACLGroup.tenant_id == current_user.tenant_id,
        )
        .group_by(ACLGroup.id)
    )
    res = await db.execute(stmt)
    out = []
    for group, count in res.all():
        resp = ACLGroupResponse.model_validate(group)
        resp.member_count = count
        out.append(resp)
    return out


@router.patch("/{group_id}", response_model=ACLGroupResponse)
@audit_action("ACL_GROUP_UPDATE", "acl_group")
async def update_acl_group(
    workspace_id: UUID,
    group_id: UUID,
    req: UpdateACLGroupRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_ACL)),
    db: AsyncSession = Depends(get_db),
) -> ACLGroupResponse:
    stmt = select(ACLGroup).where(
        ACLGroup.id == group_id,
        ACLGroup.workspace_id == workspace_id,
        ACLGroup.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    group = res.scalar_one_or_none()
    if not group:
        raise AppException(message="ACL Group not found", status_code=404)

    if req.name is not None:
        group.name = req.name
    if req.description is not None:
        group.description = req.description

    await db.commit()
    await db.refresh(group)
    return ACLGroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_200_OK)
@audit_action("ACL_GROUP_DELETE", "acl_group")
async def delete_acl_group(
    workspace_id: UUID,
    group_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_ACL)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    stmt = select(ACLGroup).where(
        ACLGroup.id == group_id,
        ACLGroup.workspace_id == workspace_id,
        ACLGroup.tenant_id == current_user.tenant_id,
    )
    res = await db.execute(stmt)
    group = res.scalar_one_or_none()
    if not group:
        raise AppException(message="ACL Group not found", status_code=404)

    if group.is_default:
        raise AppException(message="Cannot delete default 'all-members' ACL group", status_code=400)

    # Invalidate caches for all members of this group
    mem_stmt = select(ACLGroupMember.user_id).where(ACLGroupMember.group_id == group_id)
    mem_res = await db.execute(mem_stmt)
    for uid in mem_res.scalars().all():
        await invalidate_user_acl_cache(uid)

    await db.delete(group)
    await db.commit()
    return {"message": "ACL group deleted"}


@router.post("/{group_id}/members", response_model=ACLGroupMemberResponse, status_code=status.HTTP_201_CREATED)
@audit_action("ACL_GROUP_ADD_MEMBER", "acl_group_member")
async def add_group_member(
    workspace_id: UUID,
    group_id: UUID,
    req: AddGroupMemberRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_ACL)),
    db: AsyncSession = Depends(get_db),
) -> ACLGroupMemberResponse:
    # Verify group
    grp_stmt = select(ACLGroup).where(
        ACLGroup.id == group_id,
        ACLGroup.workspace_id == workspace_id,
        ACLGroup.tenant_id == current_user.tenant_id,
    )
    grp_res = await db.execute(grp_stmt)
    if not grp_res.scalar_one_or_none():
        raise AppException(message="ACL Group not found", status_code=404)

    # Verify user exists in tenant
    user_stmt = select(User).where(User.id == req.user_id, User.tenant_id == current_user.tenant_id)
    user_res = await db.execute(user_stmt)
    if not user_res.scalar_one_or_none():
        raise AppException(message="User not found in tenant", status_code=404)

    # Check already member
    check_stmt = select(ACLGroupMember).where(
        ACLGroupMember.group_id == group_id,
        ACLGroupMember.user_id == req.user_id,
    )
    check_res = await db.execute(check_stmt)
    if check_res.scalar_one_or_none():
        raise AppException(message="User is already a member of this ACL group", status_code=400)

    membership = ACLGroupMember(group_id=group_id, user_id=req.user_id)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    # Immediate cache invalidation
    await invalidate_user_acl_cache(req.user_id)

    return ACLGroupMemberResponse.model_validate(membership)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_200_OK)
@audit_action("ACL_GROUP_REMOVE_MEMBER", "acl_group_member")
async def remove_group_member(
    workspace_id: UUID,
    group_id: UUID,
    user_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_ACL)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    stmt = select(ACLGroupMember).where(
        ACLGroupMember.group_id == group_id,
        ACLGroupMember.user_id == user_id,
    )
    res = await db.execute(stmt)
    membership = res.scalar_one_or_none()
    if not membership:
        raise AppException(message="Membership not found", status_code=404)

    await db.delete(membership)
    await db.commit()

    # Immediate cache invalidation
    await invalidate_user_acl_cache(user_id)
    return {"message": "User removed from ACL group"}
