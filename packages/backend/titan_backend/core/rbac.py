import enum
from typing import Any

from titan_backend.db.models.workspaces import WorkspaceRole


class Permission(str, enum.Enum):
    SEARCH = "search"
    VIEW = "view"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    DELETE = "delete"
    REINDEX = "re-index"
    MANAGE_ACL = "manage-acl"
    MANAGE_SETTINGS = "manage-settings"
    MANAGE_MEMBERS = "manage-members"
    MANAGE_WORKSPACE = "manage-workspace"


DEFAULT_ROLE_PERMISSIONS: dict[WorkspaceRole, set[Permission]] = {
    WorkspaceRole.OWNER: {
        Permission.SEARCH,
        Permission.VIEW,
        Permission.DOWNLOAD,
        Permission.UPLOAD,
        Permission.DELETE,
        Permission.REINDEX,
        Permission.MANAGE_ACL,
        Permission.MANAGE_SETTINGS,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_WORKSPACE,
    },
    WorkspaceRole.ADMIN: {
        Permission.SEARCH,
        Permission.VIEW,
        Permission.DOWNLOAD,
        Permission.UPLOAD,
        Permission.DELETE,
        Permission.REINDEX,
        Permission.MANAGE_ACL,
        Permission.MANAGE_SETTINGS,
        Permission.MANAGE_MEMBERS,
    },
    WorkspaceRole.MEMBER: {
        Permission.SEARCH,
        Permission.VIEW,
        Permission.DOWNLOAD,
        Permission.UPLOAD,
    },
    WorkspaceRole.VIEWER: {
        Permission.SEARCH,
        Permission.VIEW,
    },
}


def check_role_permission(
    role: WorkspaceRole | str,
    permission: Permission,
    workspace_settings: dict[str, Any] | None = None,
) -> bool:
    """
    Check if a role has a given permission, taking into account workspace-level permission overrides.
    """
    if isinstance(role, str):
        try:
            role = WorkspaceRole(role.upper())
        except ValueError:
            return False

    # Check workspace-level matrix override if configured
    if workspace_settings and "permission_overrides" in workspace_settings:
        overrides = workspace_settings["permission_overrides"]
        role_overrides = overrides.get(role.value, {})
        if permission.value in role_overrides:
            return bool(role_overrides[permission.value])

    allowed = DEFAULT_ROLE_PERMISSIONS.get(role, set())
    return permission in allowed
