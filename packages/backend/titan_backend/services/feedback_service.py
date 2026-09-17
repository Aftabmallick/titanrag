from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.api.v1.events import broadcast_event
from titan_backend.db.models.chat import ChatMessage
from titan_backend.db.models.feedback import Feedback, FeedbackTriageStatus

logger = structlog.get_logger(__name__)


class FeedbackService:
    @staticmethod
    async def create_feedback(
        session: AsyncSession,
        tenant_id: UUID,
        workspace_id: UUID,
        message_id: UUID,
        rating: int,
        user_id: UUID | None = None,
        comment: str | None = None,
        corrected_answer: str | None = None,
        citation_issues: list[dict[str, Any]] | None = None,
    ) -> Feedback:
        # Check message exists and retrieve its session_id
        msg = await session.get(ChatMessage, message_id)
        if not msg:
            raise ValueError(f"Message {message_id} not found")

        feedback = Feedback(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            session_id=msg.session_id,
            message_id=message_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
            corrected_answer=corrected_answer,
            citation_issues=citation_issues or [],
            triage_status=FeedbackTriageStatus.NEW,
            details={},
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)

        # If negative rating or citation issues reported, publish event for Flywheel Triage
        if rating < 0 or (citation_issues and len(citation_issues) > 0):
            try:
                await broadcast_event(
                    "feedback.created",
                    {
                        "feedback_id": str(feedback.id),
                        "workspace_id": str(workspace_id),
                        "tenant_id": str(tenant_id),
                        "message_id": str(message_id),
                        "rating": rating,
                        "comment": comment,
                        "citation_issues": citation_issues or [],
                    },
                    tenant_id=str(tenant_id),
                )
            except Exception as e:
                logger.warning("failed_publishing_feedback_event", error=str(e))

        return feedback

    @staticmethod
    async def list_feedback(
        session: AsyncSession,
        workspace_id: UUID,
        rating: int | None = None,
        triage_status: FeedbackTriageStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Feedback], int, dict[str, Any]]:
        query = select(Feedback).where(Feedback.workspace_id == workspace_id)
        count_query = select(func.count(Feedback.id)).where(Feedback.workspace_id == workspace_id)

        if rating is not None:
            query = query.where(Feedback.rating == rating)
            count_query = count_query.where(Feedback.rating == rating)

        if triage_status is not None:
            query = query.where(Feedback.triage_status == triage_status)
            count_query = count_query.where(Feedback.triage_status == triage_status)

        query = query.order_by(Feedback.created_at.desc()).limit(limit).offset(offset)

        total = (await session.execute(count_query)).scalar() or 0
        items = (await session.execute(query)).scalars().all()

        # Compute aggregate satisfaction stats
        stats_stmt = select(
            func.coalesce(func.sum(case((Feedback.rating > 0, 1), else_=0)), 0).label("positive"),
            func.coalesce(func.sum(case((Feedback.rating < 0, 1), else_=0)), 0).label("negative"),
            func.count(Feedback.id).label("total_feedback"),
        ).where(Feedback.workspace_id == workspace_id)

        stats_row = (await session.execute(stats_stmt)).one()
        pos = stats_row.positive
        neg = stats_row.negative
        tot = stats_row.total_feedback
        sat_rate = (pos / tot * 100.0) if tot > 0 else 100.0

        aggregations = {
            "total": tot,
            "positive_count": pos,
            "negative_count": neg,
            "satisfaction_rate_percent": round(sat_rate, 1),
        }

        return list(items), total, aggregations

    @staticmethod
    async def update_triage_status(
        session: AsyncSession,
        feedback_id: UUID,
        workspace_id: UUID,
        status: FeedbackTriageStatus,
        promoted_dataset_item_id: UUID | None = None,
    ) -> Feedback:
        feedback = await session.get(Feedback, feedback_id)
        if not feedback or feedback.workspace_id != workspace_id:
            raise ValueError(f"Feedback {feedback_id} not found")

        feedback.triage_status = status
        if promoted_dataset_item_id:
            feedback.promoted_dataset_item_id = promoted_dataset_item_id

        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        return feedback
