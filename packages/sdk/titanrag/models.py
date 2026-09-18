from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Workspace(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    tenant_id: UUID
    name: str
    slug: str | None = None
    description: str | None = None
    created_at: datetime | None = None


class Document(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    filename: str
    content_type: str | None = None
    file_size_bytes: int | None = None
    status: str = "READY"
    chunk_count: int = 0
    created_at: datetime | None = None


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: UUID
    filename: str
    status: str = "PROCESSING"
    message: str = "Document uploaded successfully and queued for ingestion"


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    x: float
    y: float
    width: float
    height: float


class Citation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    citation_id: str | None = None
    document_id: UUID | str
    filename: str | None = None
    page: int | None = 1
    snippet: str
    relevance_score: float | None = None
    bbox: BoundingBox | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: UUID | str | None = None
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    latency_ms: float | None = None
    compute_units: float | None = None


# --- SSE Streaming Event Models ---


class BaseChatEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_type: str


class StatusEvent(BaseChatEvent):
    event_type: Literal["status"] = "status"
    status: str
    message: str


class TokenEvent(BaseChatEvent):
    event_type: Literal["token"] = "token"
    token: str
    index: int = 0


class CitationEvent(BaseChatEvent):
    event_type: Literal["citation"] = "citation"
    citation: Citation


class CitationVerifiedEvent(BaseChatEvent):
    event_type: Literal["citation_verified"] = "citation_verified"
    citation_id: str
    verified: bool = True
    nli_score: float = 1.0


class DoneEvent(BaseChatEvent):
    event_type: Literal["done"] = "done"
    session_id: str | None = None
    full_answer: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)


class ErrorEvent(BaseChatEvent):
    event_type: Literal["error"] = "error"
    error: str
    code: str | None = None


ChatEvent = StatusEvent | TokenEvent | CitationEvent | CitationVerifiedEvent | DoneEvent | ErrorEvent


class RAGSettingsConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    retrieval_mode: str = "HYBRID"
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    top_k: int = 20
    rerank_top_k: int = 5
    score_threshold: float = 0.40
    hyde_enabled: bool = False
    semantic_cache_enabled: bool = True
    system_prompt_override: str | None = None


class PluginConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    slug: str
    description: str | None = None
    endpoint_url: str
    hooks: list[str] = Field(default_factory=list)
    timeout_ms: int = 2000
    is_active: bool = True
    health_status: str = "HEALTHY"
    circuit_tripped: bool = False
