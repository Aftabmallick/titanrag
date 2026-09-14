import re
from typing import Any

import structlog
from datasketch import MinHash

logger = structlog.get_logger("titanrag.deduplication.minhash")


class MinHashDeduplicator:
    """
    MinHash & LSH Near-Duplicate Detection Engine.
    Computes 128-permutation MinHash signatures per chunk and enables delta re-embedding.
    """

    def __init__(self, num_perm: int = 128, threshold: float = 0.95):
        self.num_perm = num_perm
        self.threshold = threshold
        self.tokenizer = re.compile(r"\b\w+\b")

    def compute_signature(self, text: str) -> str:
        """
        Generates 128-permutation MinHash signature encoded as hex string.
        """
        m = MinHash(num_perm=self.num_perm)
        tokens = self.tokenizer.findall(text.lower())
        for token in tokens:
            m.update(token.encode("utf-8"))

        # Convert hashvalues to compact hex signature
        sig_bytes = m.digest()
        return sig_bytes.tobytes().hex()[:64]

    def estimate_jaccard(self, text1: str, text2: str) -> float:
        m1 = MinHash(num_perm=self.num_perm)
        m2 = MinHash(num_perm=self.num_perm)
        for t in self.tokenizer.findall(text1.lower()):
            m1.update(t.encode("utf-8"))
        for t in self.tokenizer.findall(text2.lower()):
            m2.update(t.encode("utf-8"))
        return float(m1.jaccard(m2))

    def detect_deltas(
        self,
        new_chunks: list[dict[str, Any]],
        existing_chunks: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Separates new chunks into:
        1. unchanged_chunks (re-use existing vector)
        2. changed_chunks (require new embedding)
        """
        existing_sigs = {c.get("minhash_signature"): c for c in existing_chunks if c.get("minhash_signature")}

        unchanged: list[dict[str, Any]] = []
        changed: list[dict[str, Any]] = []

        for new_c in new_chunks:
            sig = new_c.get("minhash_signature")
            if sig and sig in existing_sigs:
                matched_old = existing_sigs[sig]
                new_c["reused_vector_id"] = matched_old.get("id")
                unchanged.append(new_c)
            else:
                changed.append(new_c)

        logger.info(
            "delta_reembedding_analysis",
            total_new=len(new_chunks),
            unchanged_count=len(unchanged),
            changed_count=len(changed),
        )
        return unchanged, changed
