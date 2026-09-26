from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from titan_backend.core.config import settings

engine = create_async_engine(
    settings.get_database_url(),
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_pre_ping=True,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def set_session_tenant_id(session: AsyncSession, tenant_id: UUID) -> None:
    """
    Sets the session-local variable for PostgreSQL Row-Level Security.
    Safe with PgBouncer transaction pooling because it is strictly LOCAL to the transaction.

    In production: raises on failure (prevents data leakage across tenants).
    In dev/test: logs a warning and continues (supports mock/test DB backends).
    """
    from titan_backend.core.logging import logger

    try:
        await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
    except Exception as e:
        is_production = settings.ENVIRONMENT.lower() not in ("development", "dev", "test", "testing", "ci")
        if is_production:
            logger.error(
                "rls_tenant_id_set_failed",
                tenant_id=str(tenant_id),
                error=str(e),
                action="BLOCKING — request rejected to prevent cross-tenant data leak",
            )
            raise RuntimeError(
                f"CRITICAL: Failed to set RLS tenant context for tenant {tenant_id}. "
                f"Request blocked to prevent potential cross-tenant data exposure. Error: {e}"
            ) from e
        else:
            logger.warning(
                "rls_tenant_id_set_skipped",
                tenant_id=str(tenant_id),
                error=str(e),
                hint="Non-production mode — SET LOCAL not supported by test/mock DB backend",
            )


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession with automatic transaction management.
    If tenant_id is available in request state, it executes SET LOCAL app.tenant_id
    within the transaction to enforce PostgreSQL RLS.
    """
    async with async_session_factory() as session:
        tenant_id: UUID | None = getattr(request.state, "tenant_id", None) if request else None
        if tenant_id:
            await set_session_tenant_id(session, tenant_id)
        try:
            yield session
            if session.is_active:
                await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise


get_db_session = get_db
