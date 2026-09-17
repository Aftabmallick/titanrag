from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from titan_backend.db.models.chat import ChatMessage
from titan_backend.db.models.evaluation import GoldenDataset, GoldenDatasetItem
from titan_backend.db.models.feedback import Feedback, FeedbackTriageStatus

logger = structlog.get_logger(__name__)


class FlywheelTriageService:
    @staticmethod
    async def promote_feedback_to_golden(
        session: AsyncSession,
        workspace_id: UUID,
        feedback_id: UUID,
        dataset_id: UUID | None = None,
    ) -> GoldenDatasetItem:
        """Promotes a negative or corrected user feedback interaction directly into a GoldenDatasetItem."""
        feedback = await session.get(Feedback, feedback_id)
        if not feedback or feedback.workspace_id != workspace_id:
            raise ValueError(f"Feedback {feedback_id} not found")

        msg = await session.get(ChatMessage, feedback.message_id)
        if not msg:
            raise ValueError(f"Message {feedback.message_id} not found")

        # Find or use target golden dataset
        if not dataset_id:
            ds_stmt = (
                select(GoldenDataset)
                .where(GoldenDataset.workspace_id == workspace_id, GoldenDataset.is_active == True)
                .order_by(GoldenDataset.created_at.desc())
                .limit(1)
            )
            dataset = (await session.execute(ds_stmt)).scalar_one_or_none()
            if not dataset:
                # Create default flywheel dataset
                dataset = GoldenDataset(
                    tenant_id=feedback.tenant_id,
                    workspace_id=workspace_id,
                    name="Continuous Flywheel Golden Dataset",
                    description="Automatically curated test cases from user feedback and reported citation errors",
                    tags=["flywheel", "auto-generated"],
                    is_active=True,
                )
                session.add(dataset)
                await session.flush()
        else:
            dataset = await session.get(GoldenDataset, dataset_id)
            if not dataset:
                raise ValueError(f"Target GoldenDataset {dataset_id} not found")

        # Extract cited chunk IDs from assistant message
        citations = msg.citations or []
        chunk_ids = []
        doc_ids = []
        for c in citations:
            if isinstance(c, dict):
                if c.get("chunk_id"):
                    chunk_ids.append(str(c["chunk_id"]))
                if c.get("document_id"):
                    doc_ids.append(str(c["document_id"]))

        # Query text: extract prior user message from session
        query_stmt = (
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.created_at < msg.created_at,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        user_query = (await session.execute(query_stmt)).scalar_one_or_none() or "User query"

        expected_answer = feedback.corrected_answer or msg.content

        item = GoldenDatasetItem(
            dataset_id=dataset.id,
            query=user_query,
            expected_answer=expected_answer,
            expected_chunk_ids=chunk_ids,
            expected_document_ids=doc_ids,
            metadata_filters={},
            context=f"Reported issue: {feedback.comment or 'User feedback'}",
            tags=["flywheel", "regression_candidate"],
        )
        session.add(item)
        await session.flush()

        # Update feedback status
        feedback.triage_status = FeedbackTriageStatus.PROMOTED_TO_GOLDEN
        feedback.promoted_dataset_item_id = item.id
        session.add(feedback)

        await session.commit()
        await session.refresh(item)

        logger.info(
            "feedback_promoted_to_golden",
            feedback_id=str(feedback.id),
            dataset_item_id=str(item.id),
            dataset_id=str(dataset.id),
        )

        return item
