from fastapi import APIRouter

from titan_backend.api.v1.health import router as health_router
from titan_backend.api.v1.metrics import router as metrics_router

api_router = APIRouter()

# Health endpoints accessible both at root and under /api/v1
api_router.include_router(health_router)
api_router.include_router(metrics_router)
