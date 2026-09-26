import re
import time
from typing import NamedTuple
from uuid import UUID

from titan_backend.core.config import settings
from titan_backend.services.retrieval.search import SearchCandidate


class FusedCandidate(NamedTuple):
    chunk_id: UUID
    rrf_score: float
    dense_rank: int | None
    sparse_rank: int | None
    payload: dict


class TieredFusionEngine:
    """Calibrated Reciprocal Rank Fusion (RRF) with dynamic hybrid alpha weighting, recency decay, and deduplication."""

    @staticmethod
    def calculate_dynamic_alpha(query: str, base_alpha: float = 0.7) -> float:
        """Dynamically calibrates dense vs. sparse alpha based on query intent and entity density.

        Returns:
            alpha: float in [0.25, 0.85] representing dense weight (1 - alpha is BM25 sparse weight).
        """
        q = query.strip()
        if not q:
            return base_alpha

        # 1. Alphanumeric / technical entity patterns
        has_identifier = bool(
            re.search(r"[A-Za-z0-9]+[-_][A-Za-z0-9]+", q)
            or re.search(r"\b\d{3,}\b", q)
            or re.search(r"\.(md|html|json|csv|pdf|txt)\b", q, re.IGNORECASE)
            or re.search(r"\b(rfc|cve|hsm|aes|sha|md5|tls|txn|srv|manifest|audit|telemetry)\b", q, re.IGNORECASE)
        )

        has_question = bool(
            re.search(
                r"\b(what|how|why|when|where|who|explain|describe|summarize|overview|difference|guidelines)\b",
                q,
                re.IGNORECASE,
            )
        )

        words = q.split()
        if has_identifier:
            # Heavily prioritize BM25 sparse matching for exact identifiers/numbers
            return 0.35 if not has_question else 0.45
        elif has_question and len(words) >= 5:
            # Abstract semantic question with no entity tokens
            return 0.75
        elif len(words) <= 3:
            # Short concept phrase -> balanced fusion
            return 0.50
        else:
            return base_alpha

    def fuse(
        self,
        dense_candidates: list[SearchCandidate],
        sparse_candidates: list[SearchCandidate],
        query: str = "",
        alpha: float = 0.7,
        rrf_k: int = 60,
        top_k: int = 40,
        recency_decay_rate: float = 0.0,
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

        # Extract query entity signatures for metadata match boost (Phase 3)
        q_clean = query.strip().lower()
        q_nums = set(re.findall(r"\d+", q_clean))
        q_num_ints = {int(n) for n in q_nums if n.isdigit()}
        q_slugs = set(re.findall(r"[a-zA-Z0-9]+[-_][a-zA-Z0-9]+", q_clean))

        now_ts = time.time()
        scores: list[FusedCandidate] = []
        for c_id in all_chunk_ids:
            score = 0.0
            d_rank = dense_ranks.get(c_id)
            s_rank = sparse_ranks.get(c_id)

            if d_rank is not None:
                score += dense_weight * (1.0 / (rrf_k + d_rank))
            if s_rank is not None:
                score += sparse_weight * (1.0 / (rrf_k + s_rank))

            # Exact Entity / Filename Metadata Match Boost
            payload = payloads.get(c_id, {})
            fname = str(payload.get("filename", "")).lower()
            section_hier = " ".join(payload.get("section_hierarchy", [])).lower()
            cand_text = (fname + " " + section_hier).strip()

            if q_clean and fname:
                base_fname = re.sub(r"\.(md|html|json|csv|pdf|txt)$", "", fname)
                match_boost = 0.0

                # Direct filename base match in query
                if base_fname and (base_fname in q_clean or q_clean.startswith(base_fname)):
                    match_boost += 1.2

                # Numeric ID match between query and filename
                f_nums = set(re.findall(r"\d+", fname))
                f_num_ints = {int(n) for n in f_nums if n.isdigit()}
                if q_num_ints and f_num_ints and (q_num_ints & f_num_ints):
                    match_boost += 0.8

                # Technical entity slug match in section hierarchy or filename
                for slug in q_slugs:
                    if slug in cand_text:
                        match_boost += 0.5
                        break

                if match_boost > 0.0:
                    score += match_boost * (1.0 / (rrf_k + 1))

            # Temporal recency decay weighting if enabled and created_at metadata is present
            if recency_decay_rate > 0.0:
                created_at = payloads.get(c_id, {}).get("created_at")
                if created_at is not None:
                    try:
                        doc_ts = float(created_at)
                        age_days = max(0.0, (now_ts - doc_ts) / 86400.0)
                        decay_multiplier = 1.0 / (1.0 + (recency_decay_rate * age_days))
                        score *= decay_multiplier
                    except (ValueError, TypeError):
                        pass

            # Document staleness penalty (Task 6.5)
            is_stale = payloads.get(c_id, {}).get("is_stale", False)
            if is_stale:
                score *= settings.FUSION_STALENESS_PENALTY

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
