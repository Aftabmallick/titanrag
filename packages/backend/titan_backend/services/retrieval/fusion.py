from typing import NamedTuple
from uuid import UUID

from titan_backend.services.retrieval.search import SearchCandidate


class FusedCandidate(NamedTuple):
    chunk_id: UUID
    rrf_score: float
    dense_rank: int | None
    sparse_rank: int | None
    payload: dict


class TieredFusionEngine:
    """Calibrated Reciprocal Rank Fusion (RRF) with hybrid alpha weighting and deduplication."""

    def fuse(
        self,
        dense_candidates: list[SearchCandidate],
        sparse_candidates: list[SearchCandidate],
        alpha: float = 0.7,
        rrf_k: int = 60,
        top_k: int = 25,
    ) -> list[FusedCandidate]:
        # Track ranks: 1-indexed
        dense_ranks: dict[UUID, int] = {c.chunk_id: i + 1 for i, c in enumerate(dense_candidates)}
        sparse_ranks: dict[UUID, int] = {c.chunk_id: i + 1 for i, c in enumerate(sparse_candidates)}

        payloads: dict[UUID, dict] = {}
        for c in dense_candidates:
            payloads[c.chunk_id] = c.payload
        for c in sparse_candidates:
            if c.chunk_id not in payloads:
                payloads[c.chunk_id] = c.payload

        all_chunk_ids = set(dense_ranks.keys()).union(set(sparse_ranks.keys()))

        dense_weight = max(0.0, min(1.0, alpha))
        sparse_weight = 1.0 - dense_weight

        scores: list[FusedCandidate] = []
        for c_id in all_chunk_ids:
            score = 0.0
            d_rank = dense_ranks.get(c_id)
            s_rank = sparse_ranks.get(c_id)

            if d_rank is not None:
                score += dense_weight * (1.0 / (rrf_k + d_rank))
            if s_rank is not None:
                score += sparse_weight * (1.0 / (rrf_k + s_rank))

            scores.append(
                FusedCandidate(
                    chunk_id=c_id,
                    rrf_score=round(score, 6),
                    dense_rank=d_rank,
                    sparse_rank=s_rank,
                    payload=payloads.get(c_id, {}),
                )
            )

        # Sort descending by RRF score
        scores.sort(key=lambda x: x.rrf_score, reverse=True)
        return scores[:top_k]


fusion_engine = TieredFusionEngine()
