from titan_backend.core.rbac import (
    Permission,
    check_role_permission,
)
from titan_backend.db.models.workspaces import WorkspaceRole


def test_rbac_default_permission_matrix():
    # 1. OWNER has all permissions
    for perm in Permission:
        assert check_role_permission(WorkspaceRole.OWNER, perm) is True

    # 2. ADMIN has everything except manage-workspace
    assert check_role_permission(WorkspaceRole.ADMIN, Permission.UPLOAD) is True
    assert check_role_permission(WorkspaceRole.ADMIN, Permission.DELETE) is True
    assert check_role_permission(WorkspaceRole.ADMIN, Permission.MANAGE_MEMBERS) is True
    assert check_role_permission(WorkspaceRole.ADMIN, Permission.MANAGE_WORKSPACE) is False

    # 3. MEMBER has search, view, download, upload, but NOT delete or manage
    assert check_role_permission(WorkspaceRole.MEMBER, Permission.SEARCH) is True
    assert check_role_permission(WorkspaceRole.MEMBER, Permission.VIEW) is True
    assert check_role_permission(WorkspaceRole.MEMBER, Permission.DOWNLOAD) is True
    assert check_role_permission(WorkspaceRole.MEMBER, Permission.UPLOAD) is True
    assert check_role_permission(WorkspaceRole.MEMBER, Permission.DELETE) is False
    assert check_role_permission(WorkspaceRole.MEMBER, Permission.MANAGE_ACL) is False

    # 4. VIEWER only has search and view
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.SEARCH) is True
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.VIEW) is True
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.DOWNLOAD) is False
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.UPLOAD) is False
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.DELETE) is False


def test_rbac_workspace_level_override():
    # Admin can configure workspace settings to grant DOWNLOAD to VIEWER
    workspace_settings = {
        "permission_overrides": {
            "VIEWER": {
                "download": True,
            }
        }
    }
    # Default VIEWER cannot download
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.DOWNLOAD) is False
    # With override, VIEWER can download in this specific workspace
    assert check_role_permission(WorkspaceRole.VIEWER, Permission.DOWNLOAD, workspace_settings) is True
