"""Unit tests for Evaluation Framework & DeepEval Metrics — Phase 10."""

import pytest
from titan_backend.services.evaluation.deepeval_metrics import (
    DeepEvalMetrics,
    _deepeval_available,
)


def test_deepeval_availability_check():
    """Verify availability check returns a boolean without throwing."""
    avail = _deepeval_available()
    assert isinstance(avail, bool)


@pytest.mark.asyncio
async def test_deepeval_metrics_runner_evaluation():
    """DeepEval metrics runner should compute coherence, relevancy, and faithfulness."""
    runner = DeepEvalMetrics(model="mock-model")

    query = "What is the capital of France?"
    actual_output = "The capital of France is Paris."
    retrieval_context = [
        "France is a country in Western Europe. Paris is the capital and most populous city of France."
    ]

    result = await runner.compute_all(
        query=query,
        contexts=retrieval_context,
        generated_answer=actual_output,
        expected_answer="Paris",
    )

    assert result is not None
    assert result["framework"] == "deepeval"
    assert "faithfulness_deepeval" in result
    assert "contextual_relevancy_deepeval" in result
    assert "coherence_deepeval" in result
    assert 0.0 <= result["faithfulness_deepeval"] <= 1.0
    assert 0.0 <= result["contextual_relevancy_deepeval"] <= 1.0
    assert 0.0 <= result["coherence_deepeval"] <= 1.0
