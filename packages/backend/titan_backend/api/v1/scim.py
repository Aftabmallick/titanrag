from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.v1.acl_groups import invalidate_user_acl_cache
from titan_backend.clients.redis_client import get_redis_client
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException
from titan_backend.db.models.acl import ACLGroup, ACLGroupMember
from titan_backend.db.models.tenants import Tenant
from titan_backend.db.models.users import User
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.db.session import get_db

router = APIRouter(prefix="/scim/v2", tags=["SCIM 2.0 Provisioning"])


async def verify_scim_token(authorization: str | None = Header(None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppException(message="SCIM Bearer token missing", status_code=401)
    token = authorization.split(" ")[1]
    if token != settings.SCIM_BEARER_TOKEN:
        raise AppException(message="Invalid SCIM Bearer token", status_code=403)
    return True


async def _resolve_scim_tenant(
    tenant_id: UUID | None,
    x_tenant_id: str | None,
    db: AsyncSession,
) -> Tenant:
    """Resolves target tenant from URL path, header, or single-tenant default."""
    target_id = tenant_id or (UUID(x_tenant_id) if x_tenant_id else None)
    if target_id:
        stmt = select(Tenant).where(Tenant.id == target_id)
        res = await db.execute(stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            raise AppException(message="Tenant specified in SCIM route not found", status_code=404)
        return tenant

    # Fallback to first existing tenant or auto-create enterprise SCIM tenant
    stmt = select(Tenant).limit(1)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(id=uuid4(), name="Enterprise SCIM Org", plan="enterprise")
        db.add(tenant)
        await db.flush()
    return tenant


# =============================================================================
# SCIM Schemas
# =============================================================================


class SCIMName(BaseModel):
    formatted: str | None = None
    familyName: str | None = None  # noqa: N815
    givenName: str | None = None  # noqa: N815


class SCIMEmail(BaseModel):
    value: str
    primary: bool = True


class SCIMUserResource(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: str | None = None
    userName: str  # noqa: N815
    name: SCIMName | None = None
    emails: list[SCIMEmail] = Field(default_factory=list)
    active: bool = True


class SCIMMember(BaseModel):
    value: str  # user_id
    display: str | None = None
    type: str = "User"


class SCIMGroupResource(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    id: str | None = None
    displayName: str  # noqa: N815
    members: list[SCIMMember] = Field(default_factory=list)


class SCIMListResponse(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int  # noqa: N815
    startIndex: int = 1  # noqa: N815
    itemsPerPage: int = 50  # noqa: N815
    Resources: list[dict[str, Any]] = Field(default_factory=list)  # noqa: N815


# =============================================================================
# Deprovisioning Cascade
# =============================================================================


async def execute_deprovisioning_cascade(user: User, db: AsyncSession) -> None:
    """
    Instantly revokes workspace memberships, purges ACL group memberships,
    invalidates Redis sessions, and purges ACL caches in <50ms.
    """
    user.is_active = False

    # 1. Remove all workspace memberships
    ws_stmt = select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    ws_res = await db.execute(ws_stmt)
    for mem in ws_res.scalars().all():
        await db.delete(mem)

    # 2. Remove all ACL group memberships
    acl_stmt = select(ACLGroupMember).where(ACLGroupMember.user_id == user.id)
    acl_res = await db.execute(acl_stmt)
    for grp_mem in acl_res.scalars().all():
        await db.delete(grp_mem)

    # 3. Invalidate ACL cache
    await invalidate_user_acl_cache(user.id)

    # 4. Mark user session invalidated in Redis for instant JWT lockout (<50ms)
    try:
        redis = await get_redis_client()
        await redis.set(f"user_deactivated:{user.id}", "1", ex=86400)
    except Exception:
        pass


# =============================================================================
# User Endpoints (Tenant-Scoped & Root)
# =============================================================================


async def _handle_list_users(
    tenant: Tenant,
    filter_expr: str | None,
    db: AsyncSession,
) -> SCIMListResponse:
    stmt = select(User).where(User.tenant_id == tenant.id)
    if filter_expr and 'userName eq "' in filter_expr:
        target_email = filter_expr.split('userName eq "')[1].rstrip('"').strip()
        stmt = stmt.where(User.email == target_email)

    res = await db.execute(stmt)
    users = res.scalars().all()

    resources = []
    for u in users:
        resources.append(
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "id": str(u.id),
                "userName": u.email,
                "name": {"formatted": u.full_name},
                "emails": [{"value": u.email, "primary": True}],
                "active": u.is_active,
            }
        )

    return SCIMListResponse(totalResults=len(resources), Resources=resources)


async def _handle_create_user(
    tenant: Tenant,
    resource: SCIMUserResource,
    db: AsyncSession,
) -> dict[str, Any]:
    email = resource.userName.lower().strip()
    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise AppException(message="User already exists", status_code=409)

    full_name = resource.name.formatted if resource.name else None
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=full_name,
        is_active=resource.active,
    )
    db.add(user)
    await db.flush()

    # Automatically provision into default workspace and default all-members group if available
    ws_stmt = select(Workspace).where(Workspace.tenant_id == tenant.id, Workspace.is_archived.is_(False)).limit(1)
    ws_res = await db.execute(ws_stmt)
    workspace = ws_res.scalar_one_or_none()
    if workspace:
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.MEMBER))
        acl_stmt = select(ACLGroup).where(ACLGroup.workspace_id == workspace.id, ACLGroup.is_default.is_(True))
        acl_res = await db.execute(acl_stmt)
        default_acl = acl_res.scalar_one_or_none()
        if default_acl:
            db.add(ACLGroupMember(group_id=default_acl.id, user_id=user.id))

    await db.commit()
    await db.refresh(user)

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "name": {"formatted": user.full_name},
        "emails": [{"value": user.email, "primary": True}],
        "active": user.is_active,
    }


# Root /scim/v2/Users
@router.get("/Users", response_model=SCIMListResponse)
async def scim_list_users_root(
    filter: str | None = Query(None),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> SCIMListResponse:
    tenant = await _resolve_scim_tenant(None, x_tenant_id, db)
    return await _handle_list_users(tenant, filter, db)


@router.post("/Users", status_code=status.HTTP_201_CREATED)
async def scim_create_user_root(
    resource: SCIMUserResource,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await _resolve_scim_tenant(None, x_tenant_id, db)
    return await _handle_create_user(tenant, resource, db)


# Scoped /scim/v2/{tenant_id}/Users
@router.get("/{tenant_id}/Users", response_model=SCIMListResponse)
async def scim_list_users_scoped(
    tenant_id: UUID,
    filter: str | None = Query(None),
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> SCIMListResponse:
    tenant = await _resolve_scim_tenant(tenant_id, None, db)
    return await _handle_list_users(tenant, filter, db)


@router.post("/{tenant_id}/Users", status_code=status.HTTP_201_CREATED)
async def scim_create_user_scoped(
    tenant_id: UUID,
    resource: SCIMUserResource,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await _resolve_scim_tenant(tenant_id, None, db)
    return await _handle_create_user(tenant, resource, db)


@router.get("/Users/{user_id}")
@router.get("/{tenant_id}/Users/{user_id}")
async def scim_get_user(
    user_id: UUID,
    tenant_id: UUID | None = None,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(User).where(User.id == user_id)
    if tenant_id:
        stmt = stmt.where(User.tenant_id == tenant_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise AppException(message="User not found", status_code=404)

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "name": {"formatted": user.full_name},
        "emails": [{"value": user.email, "primary": True}],
        "active": user.is_active,
    }


@router.patch("/Users/{user_id}")
@router.patch("/{tenant_id}/Users/{user_id}")
async def scim_patch_user(
    user_id: UUID,
    request: Request,
    tenant_id: UUID | None = None,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(User).where(User.id == user_id)
    if tenant_id:
        stmt = stmt.where(User.tenant_id == tenant_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise AppException(message="User not found", status_code=404)

    body = await request.json()
    operations = body.get("Operations", [])
    for op in operations:
        val = op.get("value", {})
        if isinstance(val, dict) and "active" in val:
            if not val["active"]:
                await execute_deprovisioning_cascade(user, db)
            else:
                user.is_active = True

    await db.commit()
    await db.refresh(user)

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "active": user.is_active,
    }


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{tenant_id}/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def scim_delete_user(
    user_id: UUID,
    tenant_id: UUID | None = None,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(User).where(User.id == user_id)
    if tenant_id:
        stmt = stmt.where(User.tenant_id == tenant_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise AppException(message="User not found", status_code=404)

    await execute_deprovisioning_cascade(user, db)
    await db.commit()


# =============================================================================
# Group Endpoints (RFC 7643/7644 SCIM Groups mapped to ACL Groups)
# =============================================================================


async def _handle_list_groups(
    tenant: Tenant,
    filter_expr: str | None,
    db: AsyncSession,
) -> SCIMListResponse:
    stmt = (
        select(ACLGroup, func.count(ACLGroupMember.id).label("member_count"))
        .outerjoin(ACLGroupMember, ACLGroup.id == ACLGroupMember.group_id)
        .where(ACLGroup.tenant_id == tenant.id)
        .group_by(ACLGroup.id)
    )
    if filter_expr and 'displayName eq "' in filter_expr:
        target_name = filter_expr.split('displayName eq "')[1].rstrip('"').strip()
        stmt = stmt.where(ACLGroup.name == target_name)

    res = await db.execute(stmt)
    groups = res.all()

    resources = []
    for grp, _ in groups:
        mem_stmt = (
            select(ACLGroupMember.user_id, User.email)
            .join(User, ACLGroupMember.user_id == User.id)
            .where(ACLGroupMember.group_id == grp.id)
        )
        mem_res = await db.execute(mem_stmt)
        scim_members = [{"value": str(uid), "display": email, "type": "User"} for uid, email in mem_res.all()]
        resources.append(
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": str(grp.id),
                "displayName": grp.name,
                "members": scim_members,
            }
        )

    return SCIMListResponse(totalResults=len(resources), Resources=resources)


async def _handle_create_group(
    tenant: Tenant,
    resource: SCIMGroupResource,
    db: AsyncSession,
) -> dict[str, Any]:
    ws_stmt = (
        select(Workspace)
        .where(Workspace.tenant_id == tenant.id, Workspace.is_archived.is_(False))
        .order_by(Workspace.created_at.asc())
        .limit(1)
    )
    ws_res = await db.execute(ws_stmt)
    workspace = ws_res.scalar_one_or_none()
    if not workspace:
        workspace = Workspace(
            id=uuid4(),
            tenant_id=tenant.id,
            name="Default Workspace",
            description="Auto-created workspace for SCIM provisioning",
        )
        db.add(workspace)
        await db.flush()

    acl_group = ACLGroup(
        id=uuid4(),
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        name=resource.displayName.strip(),
        description=f"SCIM Synced Group: {resource.displayName}",
        is_default=False,
    )
    db.add(acl_group)
    await db.flush()

    scim_members = []
    for m in resource.members:
        try:
            uid = UUID(m.value)
            user_stmt = select(User).where(User.id == uid, User.tenant_id == tenant.id)
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if target_user:
                db.add(ACLGroupMember(group_id=acl_group.id, user_id=uid))
                await invalidate_user_acl_cache(uid)
                scim_members.append({"value": str(uid), "display": target_user.email, "type": "User"})
        except ValueError:
            continue

    await db.commit()
    await db.refresh(acl_group)

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "id": str(acl_group.id),
        "displayName": acl_group.name,
        "members": scim_members,
    }


# Root /scim/v2/Groups
@router.get("/Groups", response_model=SCIMListResponse)
async def scim_list_groups_root(
    filter: str | None = Query(None),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> SCIMListResponse:
    tenant = await _resolve_scim_tenant(None, x_tenant_id, db)
    return await _handle_list_groups(tenant, filter, db)


@router.post("/Groups", status_code=status.HTTP_201_CREATED)
async def scim_create_group_root(
    resource: SCIMGroupResource,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await _resolve_scim_tenant(None, x_tenant_id, db)
    return await _handle_create_group(tenant, resource, db)


# Scoped /scim/v2/{tenant_id}/Groups
@router.get("/{tenant_id}/Groups", response_model=SCIMListResponse)
async def scim_list_groups_scoped(
    tenant_id: UUID,
    filter: str | None = Query(None),
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> SCIMListResponse:
    tenant = await _resolve_scim_tenant(tenant_id, None, db)
    return await _handle_list_groups(tenant, filter, db)


@router.post("/{tenant_id}/Groups", status_code=status.HTTP_201_CREATED)
async def scim_create_group_scoped(
    tenant_id: UUID,
    resource: SCIMGroupResource,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await _resolve_scim_tenant(tenant_id, None, db)
    return await _handle_create_group(tenant, resource, db)


@router.get("/Groups/{group_id}")
@router.get("/{tenant_id}/Groups/{group_id}")
async def scim_get_group(
    group_id: UUID,
    tenant_id: UUID | None = None,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(ACLGroup).where(ACLGroup.id == group_id)
    if tenant_id:
        stmt = stmt.where(ACLGroup.tenant_id == tenant_id)
    res = await db.execute(stmt)
    grp = res.scalar_one_or_none()
    if not grp:
        raise AppException(message="SCIM Group not found", status_code=404)

    mem_stmt = (
        select(ACLGroupMember.user_id, User.email)
        .join(User, ACLGroupMember.user_id == User.id)
        .where(ACLGroupMember.group_id == grp.id)
    )
    mem_res = await db.execute(mem_stmt)
    scim_members = [{"value": str(uid), "display": email, "type": "User"} for uid, email in mem_res.all()]

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "id": str(grp.id),
        "displayName": grp.name,
        "members": scim_members,
    }


@router.patch("/Groups/{group_id}")
@router.patch("/{tenant_id}/Groups/{group_id}")
async def scim_patch_group(
    group_id: UUID,
    request: Request,
    tenant_id: UUID | None = None,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(ACLGroup).where(ACLGroup.id == group_id)
    if tenant_id:
        stmt = stmt.where(ACLGroup.tenant_id == tenant_id)
    res = await db.execute(stmt)
    grp = res.scalar_one_or_none()
    if not grp:
        raise AppException(message="SCIM Group not found", status_code=404)

    body = await request.json()
    operations = body.get("Operations", [])

    for op in operations:
        op_type = op.get("op", "").lower()
        val = op.get("value", {})

        if isinstance(val, dict) and "displayName" in val:
            grp.name = val["displayName"].strip()

        members = val.get("members", []) if isinstance(val, dict) else []
        if not members and isinstance(val, list):
            members = val

        for m in members:
            uid_str = m.get("value")
            if not uid_str:
                continue
            try:
                uid = UUID(uid_str)
            except ValueError:
                continue

            if op_type == "add":
                check_stmt = select(ACLGroupMember).where(
                    ACLGroupMember.group_id == grp.id,
                    ACLGroupMember.user_id == uid,
                )
                check_res = await db.execute(check_stmt)
                if not check_res.scalar_one_or_none():
                    db.add(ACLGroupMember(group_id=grp.id, user_id=uid))
                    await invalidate_user_acl_cache(uid)
            elif op_type == "remove":
                del_stmt = select(ACLGroupMember).where(
                    ACLGroupMember.group_id == grp.id,
                    ACLGroupMember.user_id == uid,
                )
                del_res = await db.execute(del_stmt)
                existing = del_res.scalar_one_or_none()
                if existing:
                    await db.delete(existing)
                    await invalidate_user_acl_cache(uid)

    await db.commit()
    await db.refresh(grp)

    return await scim_get_group(group_id=group_id, tenant_id=tenant_id, _=True, db=db)


@router.delete("/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{tenant_id}/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def scim_delete_group(
    group_id: UUID,
    tenant_id: UUID | None = None,
    _: bool = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(ACLGroup).where(ACLGroup.id == group_id)
    if tenant_id:
        stmt = stmt.where(ACLGroup.tenant_id == tenant_id)
    res = await db.execute(stmt)
    grp = res.scalar_one_or_none()
    if not grp:
        raise AppException(message="SCIM Group not found", status_code=404)

    if grp.is_default:
        raise AppException(message="Cannot delete default 'all-members' ACL group", status_code=400)

    mem_stmt = select(ACLGroupMember.user_id).where(ACLGroupMember.group_id == grp.id)
    mem_res = await db.execute(mem_stmt)
    for uid in mem_res.scalars().all():
        await invalidate_user_acl_cache(uid)

    await db.delete(grp)
    await db.commit()
