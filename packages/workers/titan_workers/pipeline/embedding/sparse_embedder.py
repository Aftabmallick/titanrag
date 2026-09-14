import re
import zlib
from collections import Counter
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.embedding.sparse")


class SparseBM25Embedder:
    """
    Qdrant-compliant BM25 Sparse Vector Generator.
    Produces sparse vectors with indices (uint32 hashed terms) and values (BM25 term weights).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, avg_doc_len: float = 250.0):
        self.k1 = k1
        self.b = b
        self.avg_doc_len = avg_doc_len
        self.token_pattern = re.compile(r"\b[a-zA-Z0-9_-]{2,}\b")

    def _hash_token(self, token: str) -> int:
        # Generate positive 32-bit unsigned integer index for Qdrant
        return zlib.crc32(token.lower().encode("utf-8")) & 0x7FFFFFFF

    def generate_sparse_vector(self, text: str) -> dict[str, list[Any]]:
        """
        Returns: {"indices": [int, ...], "values": [float, ...]}
        """
        tokens = self.token_pattern.findall(text.lower())
        if not tokens:
            return {"indices": [], "values": []}

        doc_len = len(tokens)
        counts = Counter(tokens)

        indices: list[int] = []
        values: list[float] = []

        # Sort by hashed index for consistent order
        for token, freq in sorted(counts.items()):
            token_id = self._hash_token(token)
            # Standard BM25 term frequency saturation
            tf_num = freq * (self.k1 + 1)
            tf_denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
            bm25_weight = round(tf_num / tf_denom, 4)

            indices.append(token_id)
            values.append(bm25_weight)

        return {"indices": indices, "values": values}
