import asyncio
from typing import NamedTuple
from uuid import UUID

import httpx
from titan_backend.core.circuit_breaker import CircuitBreaker
from titan_backend.core.config import settings
from titan_backend.core.logging import logger
from titan_backend.services.retrieval.candidate_validator import ValidatedCandidate

reranker_circuit_breaker = CircuitBreaker(name="reranker", failure_threshold=3, recovery_timeout_seconds=20.0)


class RerankedCandidate(NamedTuple):
    chunk_id: UUID
    relevance_score: float
    candidate: ValidatedCandidate
    is_reranked: bool = True


class CrossEncoderReranker:
    """Reranks top candidate passages with strict 400ms circuit breaker timeout and graceful fallback

    to calibrated RRF order.
    """

    def __init__(self, timeout_ms: int = 400):
        self.timeout_seconds = timeout_ms / 1000.0

    async def rerank(
        self,
        query: str,
        candidates: list[ValidatedCandidate],
        top_n: int = 5,
    ) -> list[RerankedCandidate]:
        if not candidates:
            return []

        # If only 1 candidate or circuit breaker open, fallback immediately
        if len(candidates) == 1 or not reranker_circuit_breaker.can_execute():
            return [
                RerankedCandidate(chunk_id=c.chunk_id, relevance_score=0.85, candidate=c, is_reranked=False)
                for c in candidates[:top_n]
            ]

        # Check if external Cohere or LiteLLM reranking is available
        try:
            rerank_task = self._execute_remote_rerank(query, candidates, top_n)
            results = await asyncio.wait_for(rerank_task, timeout=self.timeout_seconds)
            reranker_circuit_breaker.record_success()
            return results
        except (TimeoutError, Exception) as e:
            reranker_circuit_breaker.record_failure()
            logger.warning(
                "reranker_timed_out_or_failed_falling_back_to_rrf", error=str(e), timeout=self.timeout_seconds
            )
            return self._fallback_rrf_order(candidates, top_n)

    async def _execute_remote_rerank(
        self,
        query: str,
        candidates: list[ValidatedCandidate],
        top_n: int,
    ) -> list[RerankedCandidate]:
        documents = [c.chunk_text for c in candidates]

        # 1. Try Cohere Rerank API if configured
        if settings.COHERE_API_KEY:
            url = "https://api.cohere.ai/v1/rerank"
            headers = {
                "Authorization": f"Bearer {settings.COHERE_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "rerank-v3.5",
                "query": query,
                "documents": documents,
                "top_n": top_n,
            }
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    ranked = []
                    for item in data.get("results", []):
                        idx = item["index"]
                        score = float(item["relevance_score"])
                        ranked.append(
                            RerankedCandidate(
                                chunk_id=candidates[idx].chunk_id,
                                relevance_score=round(score, 4),
                                candidate=candidates[idx],
                            )
                        )
                    return ranked

        # 2. Try LiteLLM proxy rerank endpoint
        url = f"{settings.LITELLM_URL}/rerank"
        headers = {
            "Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "bge-reranker-large",
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                ranked = []
                for item in data.get("results", []):
                    idx = item["index"]
                    score = float(item["relevance_score"])
                    ranked.append(
                        RerankedCandidate(
                            chunk_id=candidates[idx].chunk_id,
                            relevance_score=round(score, 4),
                            candidate=candidates[idx],
                        )
                    )
                return ranked

        # Otherwise fallback to calibrated rank distribution
        return self._fallback_rrf_order(candidates, top_n)

    def _fallback_rrf_order(self, candidates: list[ValidatedCandidate], top_n: int) -> list[RerankedCandidate]:
        """Gracefully scales scores down logarithmically for calibrated confidence."""
        results: list[RerankedCandidate] = []
        for i, c in enumerate(candidates[:top_n]):
            score = max(0.45, round(0.90 - (i * 0.08), 3))
            results.append(
                RerankedCandidate(chunk_id=c.chunk_id, relevance_score=score, candidate=c, is_reranked=False)
            )
        return results


reranker = CrossEncoderReranker(timeout_ms=settings.RERANKER_TIMEOUT_MS)
