from typing import NamedTuple

from titan_backend.core.logging import logger
from titan_backend.services.retrieval.reranker import RerankedCandidate


class CRAGDecision(NamedTuple):
    passed: bool
    confidence_score: float
    reason: str
    refusal_message: str | None = None


DEFAULT_REFUSAL_MESSAGE = (
    "I could not find sufficient verified information in the provided workspace documents "
    "to answer your question with high confidence. Please verify your query or ensure the relevant "
    "documents are indexed in this workspace."
)


class CRAGConfidenceGate:
    """Corrective RAG (CRAG) Gate that evaluates top retrieval candidate confidence and rejects

    hallucinatory queries when context is missing or low-relevance.
    """

    def evaluate(
        self,
        reranked_candidates: list[RerankedCandidate],
        threshold: float = 0.40,
    ) -> CRAGDecision:
        if not reranked_candidates:
            logger.info("crag_gate_rejected_empty_candidates", threshold=threshold)
            return CRAGDecision(
                passed=False,
                confidence_score=0.0,
                reason="NO_CANDIDATES_FOUND",
                refusal_message=DEFAULT_REFUSAL_MESSAGE,
            )

        top_score = max(c.relevance_score for c in reranked_candidates)
        if top_score < threshold:
            logger.info("crag_gate_rejected_low_confidence", top_score=top_score, threshold=threshold)
            return CRAGDecision(
                passed=False,
                confidence_score=round(top_score, 4),
                reason="INSUFFICIENT_CONTEXT",
                refusal_message=DEFAULT_REFUSAL_MESSAGE,
            )

        logger.debug("crag_gate_passed", top_score=top_score, threshold=threshold)
        return CRAGDecision(
            passed=True,
            confidence_score=round(top_score, 4),
            reason="CONFIDENT",
            refusal_message=None,
        )


crag_gate = CRAGConfidenceGate()
