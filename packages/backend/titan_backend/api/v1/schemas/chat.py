from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineMode(str, Enum):
    AUTO = "auto"
    FAST = "fast"
    DEEP = "deep"


class GroundingMode(str, Enum):
    STRICT = "strict"  # Refuses to answer if context lacks verification
    BALANCED = "balanced"  # Natural synthesis strictly citing provided chunks
    CREATIVE = "creative"  # Synthesizes broadly with best-effort citations


class ChatQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000, description="User query text")
    session_id: UUID | None = Field(default=None, description="Chat session ID for multi-turn history")
    pipeline_mode: PipelineMode = Field(
        default=PipelineMode.AUTO, description="Fast-Path (<1.8s) vs Deep-Path reasoning"
    )
    grounding_mode: GroundingMode = Field(
        default=GroundingMode.BALANCED, description="Hallucination guardrail strictness"
    )
    document_ids: list[UUID] | None = Field(default=None, max_length=50, description="Explicit document scope filter")
    folder: str | None = Field(default=None, max_length=255, description="Filter by workspace folder")
    tags: list[str] | None = Field(default=None, max_length=10, description="Filter by tags")
    stream: bool = Field(default=True, description="Whether to stream response via SSE")
    temperature: float | None = Field(default=None, ge=0.0, le=1.0, description="Generation temperature override")
    model_override: str | None = Field(default=None, max_length=100, description="Model selection override")


class CitationPayload(BaseModel):
    source_index: int
    document_id: UUID
    document_name: str
    chunk_id: UUID | None = None
    page_number: int | None = None
    bbox: dict[str, Any] | None = None
    snippet: str
    relevance_score: float
    verified: bool = False
    entailment_score: float | None = None


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default="New Chat", max_length=255)
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    meta: dict[str, Any] | None = None


class ChatSessionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    user_id: UUID
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    citations: list[CitationPayload] = []
    tokens_used: int = 0
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class RegenerateRequest(BaseModel):
    fresh_retrieval: bool = Field(
        default=False, description="Whether to re-execute search or reuse existing retrieved context"
    )


class ShareSessionResponse(BaseModel):
    session_id: UUID
    share_token: str
    share_url: str


class CompareDocumentsRequest(BaseModel):
    document_a_id: UUID
    document_b_id: UUID
    topic: str = Field(
        ..., min_length=1, max_length=1000, description="Topic or question to compare across both documents"
    )
    stream: bool = Field(default=True)


class DeepResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=2000, description="Research prompt or investigation topic")
    session_id: UUID | None = None
    max_sources: int = Field(default=50, ge=5, le=100)
    system_prompt_override: str | None = None


class SharedSessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]


class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000, description="Query text to search for")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to retrieve")
    document_ids: list[UUID] | None = Field(default=None, description="Optional document filter")
    folder: str | None = Field(default=None, description="Optional folder filter")
    tags: list[str] | None = Field(default=None, description="Optional tags filter")
    doc_type: str | None = Field(default=None, description="Optional doc type filter")


class SearchCandidateResult(BaseModel):
    chunk_id: UUID
    document_id: UUID | None = None
    filename: str | None = None
    doc_type: str | None = None
    score: float
    text: str
    page_number: int | None = None


class SearchResponse(BaseModel):
    query: str
    total_results: int
    dense_latency_ms: float
    sparse_latency_ms: float
    rerank_latency_ms: float
    total_latency_ms: float
    results: list[SearchCandidateResult]
