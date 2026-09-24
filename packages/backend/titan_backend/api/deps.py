"""API dependencies re-export."""

from titan_backend.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db,
    require_admin,
    require_platform_admin,
    require_role,
    require_workspace_permission,
)

__all__ = [
    "CurrentUser",
    "get_current_user",
    "get_db",
    "require_admin",
    "require_platform_admin",
    "require_role",
    "require_workspace_permission",
]
