from fastapi import APIRouter

from titan_backend.api.v1.acl_groups import router as acl_groups_router
from titan_backend.api.v1.api_keys import router as api_keys_router
from titan_backend.api.v1.audit import router as audit_router
from titan_backend.api.v1.auth import router as auth_router
from titan_backend.api.v1.chat import router as chat_router
from titan_backend.api.v1.dlq import router as dlq_router
from titan_backend.api.v1.documents import router as documents_router
from titan_backend.api.v1.events import router as events_router
from titan_backend.api.v1.health import router as health_router
from titan_backend.api.v1.metrics import router as metrics_router
from titan_backend.api.v1.oauth import router as oauth_router
from titan_backend.api.v1.rag_settings import alt_router as rag_settings_alt_router, router as rag_settings_router
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
v1_router.include_router(documents_router)
v1_router.include_router(chat_router)
v1_router.include_router(rag_settings_router)
v1_router.include_router(rag_settings_alt_router)
v1_router.include_router(events_router)
v1_router.include_router(acl_groups_router)
v1_router.include_router(audit_router)
v1_router.include_router(scim_router)
v1_router.include_router(dlq_router)
