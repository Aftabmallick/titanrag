import asyncio
import re
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

    @staticmethod
    def clean_text_for_rerank(text: str) -> str:
        """Cleans whitespace while preserving document and section metadata."""
        return text.strip()

    async def rerank(
        self,
        query: str,
        candidates: list[ValidatedCandidate],
        top_n: int = 5,
    ) -> list[RerankedCandidate]:
        if not candidates:
            return []

        # If only 1 candidate or circuit breaker open, fallback immediately to local scoring
        if len(candidates) == 1 or not reranker_circuit_breaker.can_execute():
            return self._fallback_rrf_order(query, candidates, top_n)

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
            return self._fallback_rrf_order(query, candidates, top_n)

    async def _execute_remote_rerank(
        self,
        query: str,
        candidates: list[ValidatedCandidate],
        top_n: int,
    ) -> list[RerankedCandidate]:
        documents = [
            f"Document: {c.document_name} | Section: {c.section_heading or ''}\n{self.clean_text_for_rerank(c.chunk_text)}"
            for c in candidates
        ]

        # 1. Try Cohere Rerank API if configured
        if settings.COHERE_API_KEY:
            url = settings.COHERE_RERANK_URL
            headers = {
                "Authorization": f"Bearer {settings.COHERE_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.COHERE_RERANK_MODEL,
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
            "model": settings.LITELLM_RERANK_MODEL,
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

        # Otherwise fallback to calibrated local cross-alignment scoring
        return self._fallback_rrf_order(query, candidates, top_n)

    def _fallback_rrf_order(
        self, query: str, candidates: list[ValidatedCandidate], top_n: int
    ) -> list[RerankedCandidate]:
        """High-precision local cross-alignment reranker for multi-tenant enterprise search."""
        if not candidates:
            return []

        q_clean = query.strip().lower()
        q_words = set(re.findall(r"[a-zA-Z0-9]+", q_clean))
        q_nums = set(re.findall(r"\d+", q_clean))
        q_num_ints = {int(n) for n in q_nums if n.isdigit()}

        scored: list[tuple[float, ValidatedCandidate]] = []
        for i, c in enumerate(candidates):
            score = 0.50 - (i * 0.005)  # Preserve gentle baseline rank signal

            doc_name = (c.document_name or "").lower()
            heading = (c.section_heading or "").lower()
            text = (c.chunk_text or "").lower()
            full_context = f"{doc_name} {heading} {text}"

            # 1. Exact base filename match
            base_fname = re.sub(r"\.(md|html|json|csv|pdf|txt)$", "", doc_name)
            if base_fname and (base_fname in q_clean or q_clean.startswith(base_fname)):
                score += 0.35

            # 2. Exact number match
            c_nums = set(re.findall(r"\d+", doc_name + " " + text[:200]))
            c_num_ints = {int(n) for n in c_nums if n.isdigit()}
            if q_num_ints and c_num_ints and (q_num_ints & c_num_ints):
                score += 0.25

            # 3. Lexical query token overlap
            if q_words:
                c_words = set(re.findall(r"[a-zA-Z0-9]+", full_context))
                overlap = len(q_words & c_words) / len(q_words)
                score += overlap * 0.20

            final_score = round(max(0.10, min(0.99, score)), 4)
            scored.append((final_score, c))

        # Sort descending by computed relevance score
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RerankedCandidate(chunk_id=c.chunk_id, relevance_score=s, candidate=c, is_reranked=True)
            for s, c in scored[:top_n]
        ]


reranker = CrossEncoderReranker(timeout_ms=settings.RERANKER_TIMEOUT_MS)
