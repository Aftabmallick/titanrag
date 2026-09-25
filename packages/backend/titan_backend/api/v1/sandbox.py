"""Sandbox Session API — Phase 10.

Routes:
  POST /api/v1/sandbox/session    — create ephemeral demo session (public)
  GET  /api/v1/sandbox/session    — get current session info
  POST /api/v1/sandbox/tour       — update guided tour step
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.core.config import settings
from titan_backend.db.deps import get_db
from titan_backend.db.models.billing import SandboxSession

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/sandbox", tags=["Sandbox"])

# Sandbox limits — sourced from Settings
SANDBOX_SESSION_TTL_HOURS = settings.SANDBOX_SESSION_TTL_HOURS
SANDBOX_MAX_QUERIES_PER_HOUR = settings.SANDBOX_MAX_QUERIES_PER_HOUR
SANDBOX_MAX_UPLOADS_PER_DAY = settings.SANDBOX_MAX_UPLOADS_PER_DAY
SANDBOX_MAX_STORAGE_BYTES = settings.SANDBOX_MAX_STORAGE_BYTES
SANDBOX_MAX_SESSIONS_PER_IP_PER_DAY = settings.SANDBOX_MAX_SESSIONS_PER_IP_PER_DAY


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SandboxSessionResponse(BaseModel):
    session_id: str
    access_token: str
    workspace_id: str
    expires_at: str
    limits: dict[str, Any]
    demo_workspace_ready: bool


class SandboxSessionInfo(BaseModel):
    session_id: str
    workspace_id: str
    expires_at: str
    query_count: int
    upload_count: int
    storage_bytes: int
    tour_step: int
    limits: dict[str, Any]


class TourUpdateRequest(BaseModel):
    step: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_ip_rate_limit(client_ip: str, db: AsyncSession) -> None:
    """Reject if client IP has created ≥5 sessions today."""
    from sqlalchemy import and_, func, select

    since = datetime.now(UTC) - timedelta(days=1)
    result = await db.execute(
        select(func.count(SandboxSession.id)).where(
            and_(
                SandboxSession.client_ip == client_ip,
                SandboxSession.created_at >= since,
            )
        )
    )
    count = result.scalar() or 0
    if count >= SANDBOX_MAX_SESSIONS_PER_IP_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "SANDBOX_RATE_LIMITED",
                "message": (
                    f"Maximum {SANDBOX_MAX_SESSIONS_PER_IP_PER_DAY} sandbox sessions "
                    "per IP per day. Please sign up for a free account to continue."
                ),
            },
        )


async def _provision_ephemeral_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    """Create ephemeral tenant, workspace, and user records in Postgres.

    These are minimal records — the sandbox Celery task will seed demo docs.
    All ephemeral records are deleted by the purge_sandbox_sessions cron.
    """
    from sqlalchemy import text

    # Use raw SQL for speed — we're creating throwaway records
    await db.execute(
        text(
            """
            INSERT INTO tenants (id, name, plan, settings, created_at, updated_at)
            VALUES (:id, :name, 'SANDBOX', '{}', now(), now())
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(tenant_id),
            "name": f"sandbox-{str(tenant_id)[:8]}",
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO users (
                id, tenant_id, email, full_name, is_active,
                hashed_password, created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, :email, 'Demo User', true,
                'sandbox_no_password', now(), now()
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(user_id),
            "tenant_id": str(tenant_id),
            "email": f"demo-{str(user_id)[:8]}@{settings.SANDBOX_EMAIL_DOMAIN}",
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO workspaces (
                id, tenant_id, name, description, is_archived, settings, created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, 'Demo Workspace', 'Sandbox demo workspace', false, '{}', now(), now()
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {"id": str(workspace_id), "tenant_id": str(tenant_id)},
    )
    await db.execute(
        text(
            """
            INSERT INTO workspace_members (
                id, workspace_id, user_id, role, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), :workspace_id, :user_id, 'OWNER', now(), now()
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/session", response_model=SandboxSessionResponse)
async def create_sandbox_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SandboxSessionResponse:
    """Create an ephemeral sandbox session — no sign-up required.

    Rate-limited to 5 sessions per IP per day.
    Returns a short-lived JWT token scoped to the ephemeral workspace.
    Demo documents are seeded asynchronously.
    """
    client_ip = _get_client_ip(request)
    await _check_ip_rate_limit(client_ip, db)

    # Generate ephemeral IDs
    tenant_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(hours=SANDBOX_SESSION_TTL_HOURS)

    # Generate a JWT for the ephemeral user
    from titan_backend.api.v1.auth import create_access_token

    access_token, _ = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        email=f"demo-{str(user_id)[:8]}@{settings.SANDBOX_EMAIL_DOMAIN}",
        role="MEMBER",
        expires_delta=timedelta(hours=SANDBOX_SESSION_TTL_HOURS),
        extra_claims={"is_sandbox": True},
    )
    token_hash = _hash_token(access_token)

    # Create ephemeral DB records
    await _provision_ephemeral_tenant(db, tenant_id, workspace_id, user_id)

    # Create sandbox session record
    session = SandboxSession(
        ephemeral_tenant_id=tenant_id,
        ephemeral_workspace_id=workspace_id,
        ephemeral_user_id=user_id,
        access_token_hash=token_hash,
        client_ip=client_ip,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    # Dispatch async demo workspace seeding
    try:
        from titan_workers.tasks.sandbox_tasks import seed_sandbox_demo_workspace

        seed_sandbox_demo_workspace.apply_async(
            args=[str(session.id), str(tenant_id), str(workspace_id)],
            queue="p2_bulk_sync",
            countdown=1,  # start after response returns
        )
        demo_ready = False  # Seeding is async — client should poll
    except Exception as exc:
        logger.warning("sandbox_seeding_dispatch_failed", error=str(exc))
        demo_ready = False

    await db.commit()

    logger.info(
        "sandbox_session_created",
        session_id=str(session.id),
        client_ip=client_ip,
    )

    return SandboxSessionResponse(
        session_id=str(session.id),
        access_token=access_token,
        workspace_id=str(workspace_id),
        expires_at=expires_at.isoformat(),
        demo_workspace_ready=demo_ready,
        limits={
            "max_queries_per_hour": SANDBOX_MAX_QUERIES_PER_HOUR,
            "max_uploads_per_day": SANDBOX_MAX_UPLOADS_PER_DAY,
            "max_storage_bytes": SANDBOX_MAX_STORAGE_BYTES,
            "expires_in_hours": SANDBOX_SESSION_TTL_HOURS,
        },
    )


@router.get("/session", response_model=SandboxSessionInfo)
async def get_sandbox_session_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SandboxSessionInfo:
    """Get current sandbox session usage stats and limits."""
    # Resolve session from Authorization token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    token = auth_header[7:]
    token_hash = _hash_token(token)

    from sqlalchemy import select

    result = await db.execute(select(SandboxSession).where(SandboxSession.access_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Sandbox session not found"},
        )

    if session.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "SESSION_EXPIRED",
                "message": "Sandbox session has expired. Create a new session.",
            },
        )

    return SandboxSessionInfo(
        session_id=str(session.id),
        workspace_id=str(session.ephemeral_workspace_id),
        expires_at=session.expires_at.isoformat(),
        query_count=session.query_count,
        upload_count=session.upload_count,
        storage_bytes=session.storage_bytes,
        tour_step=session.tour_step,
        limits={
            "max_queries_per_hour": SANDBOX_MAX_QUERIES_PER_HOUR,
            "max_uploads_per_day": SANDBOX_MAX_UPLOADS_PER_DAY,
            "max_storage_bytes": SANDBOX_MAX_STORAGE_BYTES,
        },
    )


@router.post("/tour", status_code=status.HTTP_204_NO_CONTENT)
async def update_tour_step(
    body: TourUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Persist the user's guided tour progress."""
    from sqlalchemy import select, update

    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    token_hash = _hash_token(token)

    result = await db.execute(select(SandboxSession).where(SandboxSession.access_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session:
        await db.execute(update(SandboxSession).where(SandboxSession.id == session.id).values(tour_step=body.step))
        await db.commit()
