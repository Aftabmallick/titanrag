from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from titan_backend.services.chat.multimodal import MultiModalQueryProcessor, TEIBenchmarkSuite


@pytest.mark.asyncio
async def test_multimodal_query_expansion():
    processor = MultiModalQueryProcessor()

    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"visual_summary": "Architecture diagram depicting microservices and Redis queue.", '
        '"extracted_entities": ["FastAPI", "Redis PubSub", "Qdrant Vector DB"], '
        '"search_expansion_query": "How does Redis PubSub interact with Qdrant Vector DB FastAPI microservices", '
        '"suggested_filters": {"file_type": "diagram"}}'
    )
    mock_res = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"visual_summary": "Architecture diagram depicting microservices and Redis queue.", '
                        '"extracted_entities": ["FastAPI", "Redis PubSub", "Qdrant Vector DB"], '
                        '"search_expansion_query": "How does Redis PubSub interact with Qdrant Vector DB FastAPI microservices", '
                        '"suggested_filters": {"file_type": "diagram"}}'
                    )
                }
            }
        ]
    }

    with patch(
        "titan_backend.clients.litellm_client.LiteLLMClient.acompletion",
        new_callable=AsyncMock,
    ) as mock_litellm:
        mock_litellm.return_value = mock_res

        result = await processor.expand_multimodal_query(
            image_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            user_prompt="How do these components talk to each other?",
            mime_type="image/png",
        )

        assert "visual_summary" in result
        assert "extracted_entities" in result
        assert "Qdrant Vector DB" in result["extracted_entities"]
        assert "search_expansion_query" in result
        mock_litellm.assert_called_once()


@pytest.mark.asyncio
async def test_multimodal_query_fallback():
    processor = MultiModalQueryProcessor()

    with patch(
        "titan_backend.clients.litellm_client.LiteLLMClient.acompletion",
        side_effect=Exception("Vision API timeout"),
    ):
        result = await processor.expand_multimodal_query(
            image_base64="invalid_or_failing",
            user_prompt="Explain this chart",
        )
        assert "visual_summary" in result
        assert "search_expansion_query" in result
        assert "diagram" in result["extracted_entities"]


@pytest.mark.asyncio
async def test_tei_benchmark_suite():
    suite = TEIBenchmarkSuite(tei_endpoint="http://mock-tei:8081")

    stats = await suite.benchmark(batch_size=8, num_batches=3)
    assert stats["batch_size"] == 8
    assert stats["num_batches"] == 3
    assert stats["total_samples"] == 24
    assert stats["p50_ms"] > 0
    assert stats["p95_ms"] >= stats["p50_ms"]
    assert stats["p99_ms"] >= stats["p95_ms"]
    assert stats["throughput_samples_per_sec"] > 0
