"""User model and role enum definitions.

Canonical User model resides in titan_backend.db.models.users.
"""

import enum

from titan_backend.db.models.users import User


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


__all__ = ["User", "UserRole"]
