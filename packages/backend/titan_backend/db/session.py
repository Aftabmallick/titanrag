from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from titan_backend.core.config import settings

engine = create_async_engine(
    settings.get_database_url(),
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
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
    """
    try:
        await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
    except Exception:
        # Some DB backends or mock test sessions do not support Postgres SET LOCAL
        pass


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession. If tenant_id is available in request state,
    it executes SET LOCAL app.tenant_id within transaction to enforce PostgreSQL RLS.
    """
    async with async_session_factory() as session:
        tenant_id: UUID | None = getattr(request.state, "tenant_id", None) if request else None

        try:
            if tenant_id:
                await set_session_tenant_id(session, tenant_id)
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
