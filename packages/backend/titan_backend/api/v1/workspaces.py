from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from titan_backend.api.v1.acl_groups import invalidate_user_acl_cache
from titan_backend.api.v1.schemas.workspaces import (
    AddMemberRequest,
    CreateWorkspaceRequest,
    UpdateMemberRoleRequest,
    UpdateWorkspaceRequest,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from titan_backend.core.audit import audit_action
from titan_backend.core.dependencies import CurrentUser, get_current_user, require_permission
from titan_backend.core.errors import AppException
from titan_backend.core.rbac import Permission
from titan_backend.db.models.acl import ACLGroup, ACLGroupMember
from titan_backend.db.models.users import User
from titan_backend.db.models.workspaces import Workspace, WorkspaceMember, WorkspaceRole
from titan_backend.db.session import get_db

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
@audit_action("WORKSPACE_CREATE", "workspace")
async def create_workspace(
    req: CreateWorkspaceRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    workspace = Workspace(
        tenant_id=current_user.tenant_id,
        name=req.name,
        description=req.description,
        settings=req.settings,
    )
    db.add(workspace)
    await db.flush()

    # Creator is OWNER
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=WorkspaceRole.OWNER,
    )
    db.add(member)

    # Create default all-members group
    acl_group = ACLGroup(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        name="all-members",
        description="Default group containing all workspace members",
        is_default=True,
    )
    db.add(acl_group)
    await db.flush()

    # Add creator to all-members group
    db.add(ACLGroupMember(group_id=acl_group.id, user_id=current_user.id))

    await db.commit()
    await db.refresh(workspace)
    return WorkspaceResponse.model_validate(workspace)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    # Select workspaces within current tenant that user is a member of (or all if superuser)
    stmt = (
        select(Workspace)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            Workspace.tenant_id == current_user.tenant_id,
            Workspace.is_archived.is_(False),
            WorkspaceMember.user_id == current_user.id,
        )
        .order_by(Workspace.created_at.desc())
    )
    res = await db.execute(stmt)
    workspaces = res.scalars().all()
    return [WorkspaceResponse.model_validate(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.tenant_id == current_user.tenant_id,
        Workspace.is_archived.is_(False),
    )
    res = await db.execute(stmt)
    workspace = res.scalar_one_or_none()
    if not workspace:
        raise AppException(message="Workspace not found", status_code=404)
    return WorkspaceResponse.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
@audit_action("WORKSPACE_UPDATE", "workspace")
async def update_workspace(
    workspace_id: UUID,
    req: UpdateWorkspaceRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.tenant_id == current_user.tenant_id,
        Workspace.is_archived.is_(False),
    )
    res = await db.execute(stmt)
    workspace = res.scalar_one_or_none()
    if not workspace:
        raise AppException(message="Workspace not found", status_code=404)

    if req.name is not None:
        workspace.name = req.name
    if req.description is not None:
        workspace.description = req.description
    if req.settings is not None:
        workspace.settings = {**workspace.settings, **req.settings}

    await db.commit()
    await db.refresh(workspace)
    return WorkspaceResponse.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_200_OK)
@audit_action("WORKSPACE_ARCHIVE", "workspace")
async def delete_workspace(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_WORKSPACE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.tenant_id == current_user.tenant_id,
        Workspace.is_archived.is_(False),
    )
    res = await db.execute(stmt)
    workspace = res.scalar_one_or_none()
    if not workspace:
        raise AppException(message="Workspace not found", status_code=404)

    workspace.is_archived = True
    await db.commit()
    return {"message": "Workspace successfully archived"}


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW)),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceMemberResponse]:
    stmt = (
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(WorkspaceMember.workspace_id == workspace_id)
    )
    res = await db.execute(stmt)
    members = res.scalars().all()

    out = []
    for m in members:
        item = WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            email=m.user.email if m.user else None,
            created_at=m.created_at,
        )
        out.append(item)
    return out


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
@audit_action("WORKSPACE_ADD_MEMBER", "workspace_member")
async def add_workspace_member(
    workspace_id: UUID,
    req: AddMemberRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceMemberResponse:
    # 1. Find user in current tenant by email
    user_stmt = select(User).where(User.email == req.email.strip().lower(), User.tenant_id == current_user.tenant_id)
    user_res = await db.execute(user_stmt)
    target_user = user_res.scalar_one_or_none()
    if not target_user:
        raise AppException(
            message="User with this email not found in your organization",
            status_code=404,
            error_code="USER_NOT_FOUND",
        )

    # 2. Check if already member
    mem_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == target_user.id,
    )
    mem_res = await db.execute(mem_stmt)
    if mem_res.scalar_one_or_none():
        raise AppException(
            message="User is already a member of this workspace",
            status_code=400,
            error_code="MEMBER_ALREADY_EXISTS",
        )

    membership = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=target_user.id,
        role=req.role,
    )
    db.add(membership)

    # 3. Add to all-members ACL group if exists
    acl_stmt = select(ACLGroup).where(ACLGroup.workspace_id == workspace_id, ACLGroup.is_default.is_(True))
    acl_res = await db.execute(acl_stmt)
    default_acl = acl_res.scalar_one_or_none()
    if default_acl:
        db.add(ACLGroupMember(group_id=default_acl.id, user_id=target_user.id))

    await db.commit()
    await db.refresh(membership)

    return WorkspaceMemberResponse(
        id=membership.id,
        workspace_id=membership.workspace_id,
        user_id=membership.user_id,
        role=membership.role,
        email=target_user.email,
        created_at=membership.created_at,
    )


@router.patch("/{workspace_id}/members/{member_user_id}", response_model=WorkspaceMemberResponse)
@audit_action("WORKSPACE_UPDATE_MEMBER", "workspace_member")
async def update_member_role(
    workspace_id: UUID,
    member_user_id: UUID,
    req: UpdateMemberRoleRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceMemberResponse:
    mem_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == member_user_id,
    )
    res = await db.execute(mem_stmt)
    membership = res.scalar_one_or_none()
    if not membership:
        raise AppException(message="Member not found in workspace", status_code=404)

    membership.role = req.role
    await db.commit()
    await db.refresh(membership)

    return WorkspaceMemberResponse(
        id=membership.id,
        workspace_id=membership.workspace_id,
        user_id=membership.user_id,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=status.HTTP_200_OK)
@audit_action("WORKSPACE_REMOVE_MEMBER", "workspace_member")
async def remove_workspace_member(
    workspace_id: UUID,
    member_user_id: UUID,
    current_user: CurrentUser = Depends(require_permission(Permission.MANAGE_MEMBERS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    mem_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == member_user_id,
    )
    res = await db.execute(mem_stmt)
    membership = res.scalar_one_or_none()
    if not membership:
        raise AppException(message="Member not found in workspace", status_code=404)

    # 1. Clean up user's ACL group memberships in this workspace to prevent orphan permissions
    acl_stmt = (
        select(ACLGroupMember)
        .join(ACLGroup, ACLGroupMember.group_id == ACLGroup.id)
        .where(
            ACLGroup.workspace_id == workspace_id,
            ACLGroupMember.user_id == member_user_id,
        )
    )
    acl_res = await db.execute(acl_stmt)
    for agm in acl_res.scalars().all():
        await db.delete(agm)

    # 2. Invalidate ACL cache
    await invalidate_user_acl_cache(member_user_id)

    # 3. Remove workspace membership
    await db.delete(membership)
    await db.commit()
    return {"message": "Member removed from workspace"}
