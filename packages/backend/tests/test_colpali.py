from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from titan_backend.colpali.embedder import ColPaliMultiVectorEmbedder
from titan_backend.colpali.entropy_classifier import VisualEntropyClassifier
from titan_backend.colpali.retriever import ColPaliVisualRetriever


def test_visual_entropy_gating():
    # 1. Text dense page (e.g. legal agreement) -> Should NOT qualify (< 0.15)
    text_page = VisualEntropyClassifier.evaluate_page(
        page_number=1,
        text="This Master Services Agreement is entered into by and between..." * 50,
        image_count=0,
        table_count=0,
        image_area_ratio=0.0,
    )
    assert text_page.is_visual_qualified is False
    assert text_page.entropy_score < VisualEntropyClassifier.THRESHOLD

    # 2. Diagram / Chart page (e.g. architecture diagram) -> Should qualify (> 0.15)
    chart_page = VisualEntropyClassifier.evaluate_page(
        page_number=4,
        text="Figure 3.1: Microservices Topology and Network Partitioning.",
        image_count=1,
        table_count=1,
        drawing_count=12,
        image_area_ratio=0.45,
    )
    assert chart_page.is_visual_qualified is True
    assert chart_page.entropy_score >= VisualEntropyClassifier.THRESHOLD


def test_colpali_embedder_and_maxsim():
    mock_image_bytes = b"MOCK_PNG_IMAGE_BYTES_12345678"
    doc_vectors = ColPaliMultiVectorEmbedder.embed_page_image(mock_image_bytes)
    assert len(doc_vectors) == ColPaliMultiVectorEmbedder.NUM_PAGE_PATCHES
    assert len(doc_vectors[0]) == ColPaliMultiVectorEmbedder.DIMENSION

    query_vectors = ColPaliMultiVectorEmbedder.embed_query("Architecture diagram flow")
    assert len(query_vectors) == 3
    assert len(query_vectors[0]) == ColPaliMultiVectorEmbedder.DIMENSION

    # Compute MaxSim
    score = ColPaliMultiVectorEmbedder.compute_maxsim(query_vectors, doc_vectors)
    assert isinstance(score, float)
    assert -1.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_colpali_visual_retriever_mock():
    mock_hit = MagicMock()
    mock_hit.score = 0.895
    mock_hit.payload = {
        "document_id": str(uuid.uuid4()),
        "page_number": 5,
        "entropy_score": 0.42,
        "image_url": "https://minio/diagram.png",
        "description": "System architecture diagram",
    }

    with patch("titan_backend.colpali.retriever.get_qdrant_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search.return_value = [mock_hit]
        mock_get_client.return_value = mock_client

        results = await ColPaliVisualRetriever.search_visual_pages(
            tenant_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            query="Find the system architecture diagram",
        )

        assert len(results) == 1
        assert results[0]["page_number"] == 5
        assert results[0]["score"] == 0.895
        assert results[0]["caption"] == "System architecture diagram"
