from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    title: str
    source_type: str
    storage_path: str
    content_hash: str
    mime_type: str
    file_size_bytes: int
    status: str
    doc_type: str
    folder: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_stale: bool = False
    is_shared: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    limit: int


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    folder: str | None = None
    tags: list[str] | None = None
    acl_groups: list[str] | None = None
    doc_type: str | None = None
    staleness_ttl_days: int | None = None


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    task_id: UUID
    is_duplicate: bool = False
    duplicate_document_id: UUID | None = None


class URLIngestionRequest(BaseModel):
    url: str
    title: str | None = None
    folder: str | None = None
    tags: list[str] = Field(default_factory=list)
    depth: int = Field(default=0, ge=0, le=2)


class DocumentShareRequest(BaseModel):
    target_workspace_id: UUID


class IngestionPreviewRequest(BaseModel):
    file_content: str | None = None
    filename: str = "preview.txt"
    mime_type: str = "text/plain"


class IngestionPreviewChunk(BaseModel):
    index: int
    content: str
    token_count: int
    is_parent: bool = False
    context_prefix: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class IngestionPreviewResponse(BaseModel):
    filename: str
    total_chunks: int
    parent_chunks: int
    child_chunks: int
    sample_chunks: list[IngestionPreviewChunk]


class IngestionStatusResponse(BaseModel):
    document_id: UUID
    stage: str
    progress: float
    chunks_processed: int
    total_chunks: int
    error_message: str | None = None
