from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from titan_backend.db.models.feedback import FeedbackTriageStatus


class CitationIssueSchema(BaseModel):
    citation_id: str = Field(..., description="Citation identifier or pill index (e.g. '[^1]' or uuid)")
    doc_id: str | None = None
    page: int | None = None
    issue_type: str = Field("hallucinated", description="hallucinated, irrelevant, outdated_page, misquoted, other")
    comment: str | None = None


class FeedbackCreateRequest(BaseModel):
    rating: int = Field(..., description="1 for positive, -1 for negative")
    comment: str | None = None
    corrected_answer: str | None = None
    citation_issues: list[CitationIssueSchema] = Field(default_factory=list)


class FeedbackTriageRequest(BaseModel):
    triage_status: FeedbackTriageStatus


class FeedbackResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    session_id: UUID
    message_id: UUID
    user_id: UUID | None
    rating: int
    comment: str | None
    corrected_answer: str | None
    citation_issues: list[dict[str, Any]]
    triage_status: FeedbackTriageStatus
    promoted_dataset_item_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
