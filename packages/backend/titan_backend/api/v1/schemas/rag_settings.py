from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalStrategy(str, Enum):
    HYBRID = "HYBRID"
    DENSE_ONLY = "DENSE_ONLY"
    SPARSE_ONLY = "SPARSE_ONLY"


class RAGSettingsUpdate(BaseModel):
    retrieval_mode: RetrievalStrategy | None = Field(default=None, description="Search strategy")
    dense_weight: float | None = Field(default=None, ge=0.0, le=1.0, description="Dense vector weight (alpha)")
    sparse_weight: float | None = Field(default=None, ge=0.0, le=1.0, description="Sparse vector weight")
    top_k: int | None = Field(default=None, ge=5, le=100, description="Number of initial candidates to retrieve")
    rerank_top_k: int | None = Field(default=None, ge=1, le=25, description="Number of candidates after reranking")
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0, description="CRAG confidence gate threshold")
    context_window_strategy: str | None = Field(default=None, max_length=50, description="HIERARCHICAL, FLATTENED, etc.")
    parent_context_enabled: bool | None = Field(default=None, description="Inject parent chunk text")
    hyde_enabled: bool | None = Field(default=None, description="Hypothetical Document Embeddings toggle")
    semantic_cache_enabled: bool | None = Field(default=None, description="Enable ACL-salted semantic caching")
    cache_cosine_threshold: float | None = Field(default=None, ge=0.80, le=1.0, description="Cosine threshold for semantic cache")
    cache_ttl_seconds: int | None = Field(default=None, ge=60, le=604800, description="Cache TTL in seconds")
    system_prompt_override: str | None = Field(default=None, max_length=10000, description="Custom system prompt override")


class RAGSettingsResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    retrieval_mode: str
    dense_weight: float
    sparse_weight: float
    top_k: int
    rerank_top_k: int
    score_threshold: float
    context_window_strategy: str
    parent_context_enabled: bool = False
    hyde_enabled: bool = False
    semantic_cache_enabled: bool = True
    cache_cosine_threshold: float = 0.95
    cache_ttl_seconds: int = 86400
    system_prompt_override: str | None = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)
