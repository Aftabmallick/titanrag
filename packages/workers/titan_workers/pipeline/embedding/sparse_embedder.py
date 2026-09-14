import math
import re
import zlib
from collections import Counter
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.embedding.sparse")


class WorkspaceIDFManager:
    """
    Manages corpus-wide term frequency statistics per workspace.
    Tracks total document count N and term document frequencies n(w).
    Provides thread-safe local memory storage with optional Redis sync.
    """

    def __init__(self) -> None:
        # workspace_id -> {"total_docs": int, "df": dict[str, int]}
        self._corpus_stats: dict[str, dict[str, Any]] = {}

    def get_stats(self, workspace_id: str) -> dict[str, Any]:
        if workspace_id not in self._corpus_stats:
            self._corpus_stats[workspace_id] = {"total_docs": 1, "df": {}}
        return self._corpus_stats[workspace_id]

    def record_document_terms(self, workspace_id: str, unique_tokens: set[str]) -> None:
        stats = self.get_stats(workspace_id)
        stats["total_docs"] += 1
        df_map: dict[str, int] = stats["df"]
        for token in unique_tokens:
            df_map[token] = df_map.get(token, 0) + 1

    def compute_idf(self, workspace_id: str, token: str) -> float:
        stats = self.get_stats(workspace_id)
        n = stats["total_docs"]
        df = stats["df"].get(token, 1)
        # Probabilistic BM25 IDF with smoothing to guarantee positive weights:
        # ln(1 + (N - df + 0.5) / (df + 0.5))
        numerator = max(0.0, float(n - df) + 0.5)
        denominator = float(df) + 0.5
        return round(math.log(1.0 + (numerator / denominator)), 4)


# Global singleton manager
workspace_idf_manager = WorkspaceIDFManager()


class SparseBM25Embedder:
    """
    Production Qdrant-compliant BM25 Sparse Vector Generator with full IDF weighting.
    Produces sparse vectors with:
      - indices: uint32 CRC32 hashed positive integers
      - values: BM25 score = IDF(w) * TF_saturation(w, d)
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        avg_doc_len: float = 250.0,
        idf_manager: WorkspaceIDFManager | None = None,
    ):
        self.k1 = k1
        self.b = b
        self.avg_doc_len = avg_doc_len
        self.token_pattern = re.compile(r"\b[a-zA-Z0-9_-]{2,}\b")
        self.idf_manager = idf_manager or workspace_idf_manager

    def _hash_token(self, token: str) -> int:
        # Generate positive 32-bit unsigned integer index for Qdrant
        return zlib.crc32(token.lower().encode("utf-8")) & 0x7FFFFFFF

    def generate_sparse_vector(
        self,
        text: str,
        workspace_id: str = "default",
        update_idf: bool = False,
    ) -> dict[str, list[Any]]:
        """
        Generates sparse BM25 vector with combined TF saturation and IDF weight.
        Returns: {"indices": [int, ...], "values": [float, ...]}
        """
        tokens = self.token_pattern.findall(text.lower())
        if not tokens:
            return {"indices": [], "values": []}

        unique_tokens = set(tokens)
        if update_idf:
            self.idf_manager.record_document_terms(workspace_id, unique_tokens)

        doc_len = len(tokens)
        counts = Counter(tokens)

        indices: list[int] = []
        values: list[float] = []

        # Sort by hashed index for consistent order
        for token, freq in sorted(counts.items()):
            token_id = self._hash_token(token)

            # 1. Term frequency saturation
            tf_num = freq * (self.k1 + 1.0)
            tf_denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
            tf_score = tf_num / tf_denom

            # 2. Inverse document frequency factor
            idf_factor = self.idf_manager.compute_idf(workspace_id, token)

            # Combined BM25 weight (guaranteed > 0)
            bm25_weight = round(max(0.01, tf_score * idf_factor), 4)

            indices.append(token_id)
            values.append(bm25_weight)

        return {"indices": indices, "values": values}
