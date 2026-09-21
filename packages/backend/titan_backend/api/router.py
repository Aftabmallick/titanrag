from fastapi import APIRouter

from titan_backend.api.v1.ab_testing import router as ab_testing_router
from titan_backend.api.v1.acl_groups import router as acl_groups_router
from titan_backend.api.v1.analytics import router as analytics_router
from titan_backend.api.v1.api_keys import router as api_keys_router
from titan_backend.api.v1.audit import router as audit_router
from titan_backend.api.v1.auth import router as auth_router
from titan_backend.api.v1.chat import router as chat_router
from titan_backend.api.v1.collaboration import router as collaboration_router
from titan_backend.api.v1.compliance import router as compliance_router
from titan_backend.api.v1.connectors import router as connectors_router
from titan_backend.api.v1.dlq import router as dlq_router
from titan_backend.api.v1.documents import router as documents_router
from titan_backend.api.v1.evaluation import router as evaluation_router
from titan_backend.api.v1.events import router as events_router
from titan_backend.api.v1.feedback import router as feedback_router
from titan_backend.api.v1.file_security import router as file_security_router
from titan_backend.api.v1.finops import router as finops_router
from titan_backend.api.v1.graph import router as graph_router
from titan_backend.api.v1.health import router as health_router
from titan_backend.api.v1.integrations import router as integrations_router
from titan_backend.api.v1.kms import router as kms_router
from titan_backend.api.v1.media import router as media_router
from titan_backend.api.v1.metrics import router as metrics_router
from titan_backend.api.v1.multimodal import router as multimodal_router
from titan_backend.api.v1.oauth import router as oauth_router
from titan_backend.api.v1.plugins import router as plugins_router
from titan_backend.api.v1.prompts import router as prompts_router
from titan_backend.api.v1.rag_settings import alt_router as rag_settings_alt_router
from titan_backend.api.v1.rag_settings import router as rag_settings_router
from titan_backend.api.v1.residency import router as residency_router
from titan_backend.api.v1.retention import router as retention_router
from titan_backend.api.v1.saml import router as saml_router
from titan_backend.api.v1.scim import router as scim_router
from titan_backend.api.v1.visual_pages import router as visual_pages_router
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

# Phase 6 Routers
v1_router.include_router(feedback_router)
v1_router.include_router(finops_router)
v1_router.include_router(prompts_router)
v1_router.include_router(ab_testing_router)
v1_router.include_router(evaluation_router)
v1_router.include_router(analytics_router)

# Phase 7 Routers
v1_router.include_router(plugins_router)

# Phase 8 Routers

v1_router.include_router(connectors_router)
v1_router.include_router(saml_router)
v1_router.include_router(integrations_router)
v1_router.include_router(graph_router)
v1_router.include_router(media_router)
v1_router.include_router(visual_pages_router)
v1_router.include_router(collaboration_router)
v1_router.include_router(multimodal_router)

# Phase 9 Routers
v1_router.include_router(compliance_router)
v1_router.include_router(retention_router)
v1_router.include_router(kms_router)
v1_router.include_router(residency_router)
v1_router.include_router(file_security_router)
