"""System Announcements API — Phase 10.

Provides endpoints for creating, retrieving, and managing system-wide
broadcast announcements for all or specific tenants.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from titan_backend.api.deps import get_current_user, get_db
from titan_backend.db.models.billing import AnnouncementSeverity, SystemAnnouncement
from titan_backend.db.models.user import User

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["announcements"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=256)
    body: str
    severity: AnnouncementSeverity = AnnouncementSeverity.INFO
    target_tenant_ids: list[str] | None = None
    action_url: str | None = Field(None, max_length=512)
    action_label: str | None = Field(None, max_length=64)
    expires_at: datetime | None = None


class AnnouncementResponse(BaseModel):
    id: UUID
    title: str
    body: str
    severity: AnnouncementSeverity
    target_tenant_ids: list[str] | None = None
    action_url: str | None = None
    action_label: str | None = None
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/announcements", response_model=list[AnnouncementResponse])
async def list_active_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SystemAnnouncement]:
    """Retrieve all currently active announcements visible to the caller's tenant."""
    now = datetime.now(UTC)
    tenant_str = str(current_user.tenant_id)

    stmt = (
        select(SystemAnnouncement)
        .where(
            SystemAnnouncement.is_active.is_(True),
            or_(
                SystemAnnouncement.expires_at.is_(None),
                SystemAnnouncement.expires_at > now,
            ),
        )
        .order_by(SystemAnnouncement.created_at.desc())
    )
    result = await db.execute(stmt)
    all_announcements = result.scalars().all()

    # Filter target tenants if targeted
    visible = []
    for a in all_announcements:
        if not a.target_tenant_ids or tenant_str in a.target_tenant_ids:
            visible.append(a)
    return visible


@router.post(
    "/platform/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_system_announcement(
    data: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SystemAnnouncement:
    """Create a new platform-wide announcement. Requires super-admin privileges."""
    announcement = SystemAnnouncement(
        title=data.title,
        body=data.body,
        severity=data.severity,
        target_tenant_ids=data.target_tenant_ids,
        action_url=data.action_url,
        action_label=data.action_label,
        expires_at=data.expires_at,
        created_by_id=current_user.id,
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)

    logger.info(
        "system_announcement_created",
        announcement_id=str(announcement.id),
        severity=announcement.severity.value,
        title=announcement.title,
    )
    return announcement


@router.delete(
    "/platform/announcements/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="announcements_deactivate_announcement",
)
async def deactivate_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Deactivate an active system announcement."""
    stmt = update(SystemAnnouncement).where(SystemAnnouncement.id == announcement_id).values(is_active=False)
    result = await db.execute(stmt)
    if getattr(result, "rowcount", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Announcement {announcement_id} not found",
        )
    await db.commit()
    logger.info("system_announcement_deactivated", announcement_id=str(announcement_id))
