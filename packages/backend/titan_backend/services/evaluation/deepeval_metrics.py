"""DeepEval Integration — Phase 10.

Implements DeepEval metrics alongside RAGAS for multi-framework evaluation:
- G-Eval Coherence
- Contextual Relevancy
- Hallucination Score (inverse of faithfulness)
- Faithfulness (DeepEval's LLM-based version)

Stored with framework tag so results from RAGAS and DeepEval can be
compared side-by-side.

Design: optional import — if deepeval is not installed, falls back to
a lightweight heuristic estimator with a clear warning in the logs.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Framework availability check
# ---------------------------------------------------------------------------


def _deepeval_available() -> bool:
    try:
        import deepeval  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# DeepEval Metrics Runner
# ---------------------------------------------------------------------------


class DeepEvalMetrics:
    """Wraps DeepEval metric computation with graceful fallback.

    When DeepEval is available, uses LLM-based evaluation (G-Eval).
    When not available, returns heuristic estimates with a DEGRADED flag.
    """

    FRAMEWORK = "deepeval"
    FRAMEWORK_VERSION: str = "unknown"

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        """
        Args:
            model: LLM model to use for DeepEval judge (G-Eval).
                   Defaults to gpt-4o-mini for cost efficiency.
        """
        self.model = model
        self._available = _deepeval_available()
        if not self._available:
            logger.warning(
                "deepeval_not_installed",
                message="deepeval package not found. Install with: pip install deepeval",
            )
        else:
            try:
                import deepeval

                self.FRAMEWORK_VERSION = getattr(deepeval, "__version__", "unknown")
            except Exception:
                pass

    async def compute_all(
        self,
        query: str,
        contexts: list[str],
        generated_answer: str,
        expected_answer: str | None = None,
    ) -> dict[str, Any]:
        """Compute all DeepEval metrics for a single RAG response.

        Returns a dict with metric names as keys and scores as values.
        All scores are 0.0–1.0 (higher = better), except hallucination
        (lower = better, so we invert it to a faithfulness_deepeval score).

        Args:
            query: The user's input question
            contexts: List of retrieved context strings
            generated_answer: The LLM-generated answer
            expected_answer: Ground truth answer (optional — enables G-Eval on gold)

        Returns:
            {
                "framework": "deepeval",
                "framework_version": "1.x.x",
                "is_degraded": False,
                "faithfulness_deepeval": 0.87,
                "contextual_relevancy_deepeval": 0.72,
                "coherence_deepeval": 0.91,
                "hallucination_deepeval": 0.13,   # raw hallucination (lower = better)
            }
        """
        if not self._available:
            return self._heuristic_fallback(query, contexts, generated_answer)

        try:
            return await self._compute_with_deepeval(
                query=query,
                contexts=contexts,
                generated_answer=generated_answer,
                expected_answer=expected_answer,
            )
        except Exception as exc:
            logger.error("deepeval_computation_failed", error=str(exc))
            return self._heuristic_fallback(query, contexts, generated_answer)

    async def _compute_with_deepeval(
        self,
        query: str,
        contexts: list[str],
        generated_answer: str,
        expected_answer: str | None,
    ) -> dict[str, Any]:
        """Run actual DeepEval metrics using the LLM judge."""
        from deepeval.metrics import (  # type: ignore[import-untyped]
            ContextualRelevancyMetric,
            FaithfulnessMetric,
            HallucinationMetric,
        )
        from deepeval.test_case import LLMTestCase  # type: ignore[import-untyped]

        test_case = LLMTestCase(
            input=query,
            actual_output=generated_answer,
            expected_output=expected_answer or "",
            retrieval_context=contexts,
        )

        # Initialize metrics with our judge model
        faithfulness = FaithfulnessMetric(
            threshold=0.5,
            model=self.model,
            include_reason=True,
        )
        hallucination = HallucinationMetric(
            threshold=0.3,
            model=self.model,
        )
        contextual_relevancy = ContextualRelevancyMetric(
            threshold=0.5,
            model=self.model,
        )

        # Run evaluation (synchronous within DeepEval's asyncio handling)
        for metric in [faithfulness, hallucination, contextual_relevancy]:
            metric.measure(test_case)

        # G-Eval coherence (if expected answer available)
        coherence_score = 1.0
        if expected_answer:
            try:
                from deepeval.metrics import GEval  # type: ignore[import-untyped]
                from deepeval.test_case import LLMTestCaseParams  # type: ignore[import-untyped]

                g_eval = GEval(
                    name="Coherence",
                    model=self.model,
                    criteria=(
                        "Coherence: The response is logically structured, well-organized and easy to understand."
                    ),
                    evaluation_params=[
                        LLMTestCaseParams.INPUT,
                        LLMTestCaseParams.ACTUAL_OUTPUT,
                    ],
                )
                g_eval.measure(test_case)
                coherence_score = g_eval.score or 1.0
            except Exception as exc:
                logger.warning("geval_coherence_failed", error=str(exc))

        faithfulness_score = getattr(faithfulness, "score", 0.0) or 0.0
        hallucination_score = getattr(hallucination, "score", 0.0) or 0.0
        relevancy_score = getattr(contextual_relevancy, "score", 0.0) or 0.0

        return {
            "framework": self.FRAMEWORK,
            "framework_version": self.FRAMEWORK_VERSION,
            "is_degraded": False,
            "faithfulness_deepeval": round(float(faithfulness_score), 4),
            "contextual_relevancy_deepeval": round(float(relevancy_score), 4),
            "coherence_deepeval": round(float(coherence_score), 4),
            "hallucination_deepeval": round(float(hallucination_score), 4),
            "faithfulness_reason": getattr(faithfulness, "reason", None),
        }

    def _heuristic_fallback(
        self,
        query: str,
        contexts: list[str],
        generated_answer: str,
    ) -> dict[str, Any]:
        """Lightweight heuristic estimates when DeepEval is not installed.

        These are NOT LLM-based — they're simple overlap metrics.
        The is_degraded flag signals that real DeepEval should be installed.
        """

        # Approximate context relevancy: word overlap between contexts and query
        all_context = " ".join(contexts).lower()
        q_words = set(query.lower().split())
        c_words = set(all_context.split())
        relevancy = min(1.0, len(q_words & c_words) / max(len(q_words), 1))

        # Approximate faithfulness: answer tokens present in context
        a_words = set(generated_answer.lower().split())
        stopwords = {"the", "a", "an", "is", "in", "of", "and", "to", "that", "for"}
        a_sig = a_words - stopwords
        c_sig = c_words - stopwords
        faithfulness = min(1.0, len(a_sig & c_sig) / max(len(a_sig), 1))

        return {
            "framework": self.FRAMEWORK,
            "framework_version": "heuristic-fallback",
            "is_degraded": True,
            "faithfulness_deepeval": round(faithfulness, 4),
            "contextual_relevancy_deepeval": round(relevancy, 4),
            "coherence_deepeval": 0.0,  # Cannot estimate without LLM
            "hallucination_deepeval": round(1.0 - faithfulness, 4),
        }


# ---------------------------------------------------------------------------
# Multi-Framework Aggregator
# ---------------------------------------------------------------------------


async def run_multi_framework_evaluation(
    query: str,
    contexts: list[str],
    generated_answer: str,
    retrieved_chunk_ids: list[str],
    ground_truth_chunk_ids: list[str],
    expected_answer: str | None = None,
    frameworks: list[str] | None = None,
    llm_judge_model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """Run evaluation with one or both frameworks and return combined results.

    Args:
        frameworks: ["ragas", "deepeval", "both"] — defaults to "both"

    Returns:
        Combined dict with all metric scores, tagged by framework.
        Framework-specific keys are suffixed with _ragas or _deepeval.
    """
    if frameworks is None:
        frameworks = ["both"]

    run_ragas = "ragas" in frameworks or "both" in frameworks
    run_deepeval = "deepeval" in frameworks or "both" in frameworks

    results: dict[str, Any] = {
        "query": query,
        "frameworks_used": [],
        "all_scores": {},
    }

    # RAGAS metrics (already implemented in Phase 6)
    if run_ragas:
        try:
            from titan_backend.services.evaluation.metrics import (
                calculate_answer_relevancy_heuristic,
                calculate_context_precision,
                calculate_context_recall,
            )

            ragas_scores = {
                "context_precision_ragas": calculate_context_precision(
                    retrieved_chunk_ids, ground_truth_chunk_ids, k=5
                ),
                "context_recall_ragas": calculate_context_recall(retrieved_chunk_ids, ground_truth_chunk_ids),
                "answer_relevancy_ragas": calculate_answer_relevancy_heuristic(query, generated_answer),
            }
            results["all_scores"].update(ragas_scores)
            results["frameworks_used"].append("ragas")
        except Exception as exc:
            logger.error("ragas_evaluation_failed", error=str(exc))

    # DeepEval metrics
    if run_deepeval:
        try:
            de = DeepEvalMetrics(model=llm_judge_model)
            deepeval_scores = await de.compute_all(
                query=query,
                contexts=contexts,
                generated_answer=generated_answer,
                expected_answer=expected_answer,
            )
            results["all_scores"].update(deepeval_scores)
            results["frameworks_used"].append("deepeval")
        except Exception as exc:
            logger.error("deepeval_evaluation_failed", error=str(exc))

    # Aggregate: average faithfulness across frameworks (the primary quality signal)
    faithfulness_scores = []
    for k, v in results["all_scores"].items():
        if "faithfulness" in k and isinstance(v, (int, float)) and not isinstance(v, bool):
            faithfulness_scores.append(float(v))

    if faithfulness_scores:
        results["faithfulness_aggregate"] = round(sum(faithfulness_scores) / len(faithfulness_scores), 4)

    return results
