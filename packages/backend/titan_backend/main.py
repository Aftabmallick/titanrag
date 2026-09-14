import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from titan_backend.api.router import api_router
from titan_backend.api.v1.metrics import REQUEST_COUNT, REQUEST_LATENCY
from titan_backend.clients.qdrant_client import init_qdrant_collection
from titan_backend.clients.redis_client import close_redis_pool
from titan_backend.core.config import settings
from titan_backend.core.errors import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from titan_backend.core.logging import logger, setup_logging
from titan_backend.core.security_headers import SecurityAndCorrelationMiddleware
from titan_backend.core.telemetry import init_telemetry
from titan_backend.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Setup structured logging
    setup_logging(log_level=settings.LOG_LEVEL, json_format=not settings.DEBUG)
    logger.info("application_starting", app_name=settings.APP_NAME, environment=settings.ENVIRONMENT)

    # Initialize OpenTelemetry
    init_telemetry(app, engine)

    # Provision Qdrant collection and payload indexes
    try:
        await init_qdrant_collection()
    except Exception as e:
        logger.warning("qdrant_collection_init_deferred", error=str(e))

    logger.info("application_startup_complete")
    yield

    # Teardown
    logger.info("application_shutting_down")
    await close_redis_pool()
    await engine.dispose()
    logger.info("application_shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TitanRAG API",
        description="Enterprise Multi-Tenant Multimodal RAG Engine with Defense-in-Depth and Transactional Outbox",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Security Headers and Request ID
    app.add_middleware(SecurityAndCorrelationMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Metrics Middleware
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):  # type: ignore
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        handler = request.url.path
        method = request.method
        status_code = str(response.status_code)

        REQUEST_COUNT.labels(method=method, handler=handler, status=status_code).inc()
        REQUEST_LATENCY.labels(method=method, handler=handler).observe(duration)

        return response

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Router mounting
    app.include_router(api_router)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_app()
