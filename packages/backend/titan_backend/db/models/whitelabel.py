"""White-label branding models re-export.

Canonical definitions reside in titan_backend.db.models.billing.
"""

from titan_backend.db.models.billing import TenantBrandConfig

__all__ = ["TenantBrandConfig"]
