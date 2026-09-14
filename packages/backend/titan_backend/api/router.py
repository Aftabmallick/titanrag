from fastapi import APIRouter

from titan_backend.api.v1.acl_groups import router as acl_groups_router
from titan_backend.api.v1.api_keys import router as api_keys_router
from titan_backend.api.v1.audit import router as audit_router
from titan_backend.api.v1.auth import router as auth_router
from titan_backend.api.v1.health import router as health_router
from titan_backend.api.v1.metrics import router as metrics_router
from titan_backend.api.v1.oauth import router as oauth_router
from titan_backend.api.v1.scim import router as scim_router
from titan_backend.api.v1.workspaces import router as workspaces_router

# Root router for unversioned probes
root_router = APIRouter()
root_router.include_router(health_router)
root_router.include_router(metrics_router)

# Versioned /api/v1 router
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(metrics_router)
v1_router.include_router(auth_router)
v1_router.include_router(oauth_router)
v1_router.include_router(api_keys_router)
v1_router.include_router(workspaces_router)
v1_router.include_router(acl_groups_router)
v1_router.include_router(audit_router)
v1_router.include_router(scim_router)
