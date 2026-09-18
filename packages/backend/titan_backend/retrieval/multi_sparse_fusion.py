from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class RankedCandidate:
    chunk_id: str
    document_id: str
    content: str
    score: float
    rank: int
    metadata: dict[str, Any]


class MultiSparseHybridFusion:
    """
    Multi-Sparse Reciprocal Rank Fusion (RRF).
    Combines dense semantic vectors, BM25 keyword matching, and SPLADE neural sparse expansion:
    RRF(d) = alpha / (60 + r_dense) + beta / (60 + r_bm25) + gamma / (60 + r_splade)
    """

    K_RRF = 60

    @classmethod
    def fuse_rankings(
        cls,
        dense_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        splade_results: list[dict[str, Any]],
        alpha: float = 1.0,
        beta: float = 0.5,
        gamma: float = 0.8,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        scores: dict[str, float] = defaultdict(float)
        candidate_meta: dict[str, dict[str, Any]] = {}

        # 1. Score Dense candidates
        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk_id"]
            scores[cid] += alpha / (cls.K_RRF + rank)
            if cid not in candidate_meta:
                candidate_meta[cid] = item

        # 2. Score BM25 candidates
        for rank, item in enumerate(bm25_results, start=1):
            cid = item["chunk_id"]
            scores[cid] += beta / (cls.K_RRF + rank)
            if cid not in candidate_meta:
                candidate_meta[cid] = item

        # 3. Score SPLADE candidates
        for rank, item in enumerate(splade_results, start=1):
            cid = item["chunk_id"]
            scores[cid] += gamma / (cls.K_RRF + rank)
            if cid not in candidate_meta:
                candidate_meta[cid] = item

        # Sort descending by fused score
        sorted_cids = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        fused: list[dict[str, Any]] = []
        for rank, (cid, fused_score) in enumerate(sorted_cids, start=1):
            item_copy = dict(candidate_meta[cid])
            item_copy["fused_score"] = round(fused_score, 6)
            item_copy["fused_rank"] = rank
            fused.append(item_copy)

        return fused
