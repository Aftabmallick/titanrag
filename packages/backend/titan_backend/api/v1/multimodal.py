from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from titan_backend.api.v1.auth import get_current_user
from titan_backend.services.chat.multimodal import MultiModalQueryProcessor, TEIBenchmarkSuite

router = APIRouter(prefix="/chat/multimodal", tags=["Multi-Modal Querying"])


class MultiModalQueryRequest(BaseModel):
    user_prompt: str = Field(..., description="User's textual query/prompt")
    image_base64: str = Field(..., description="Base64 encoded image string")
    mime_type: str = Field(default="image/png", description="Image MIME type (e.g. image/png, image/jpeg)")
    workspace_id: str | None = Field(default=None, description="Target workspace ID")


class TEIBenchmarkRequest(BaseModel):
    batch_size: int = Field(default=16, ge=1, le=128)
    num_batches: int = Field(default=5, ge=1, le=50)
    tei_endpoint: str = Field(default="http://localhost:8081")


@router.post("/query")
async def expand_multimodal_query_endpoint(
    body: MultiModalQueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Expands an image query (e.g. diagram or table screenshot) with structured search keywords and OCR context.
    """
    processor = MultiModalQueryProcessor()
    result = await processor.expand_multimodal_query(
        image_base64=body.image_base64,
        user_prompt=body.user_prompt,
        mime_type=body.mime_type,
    )
    return {
        "status": "success",
        "data": result,
    }


@router.post("/benchmark-tei")
async def benchmark_tei_endpoint(
    body: TEIBenchmarkRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Executes a latency & throughput benchmark against a Text Embeddings Inference (TEI) instance.
    """
    suite = TEIBenchmarkSuite(tei_endpoint=body.tei_endpoint)
    stats = await suite.benchmark(
        batch_size=body.batch_size,
        num_batches=body.num_batches,
    )
    return {
        "status": "success",
        "data": stats,
    }
