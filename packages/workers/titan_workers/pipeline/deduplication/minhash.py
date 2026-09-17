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
        hex_str: str = sig_bytes.tobytes().hex()
        return hex_str[:64]

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


class WorkspaceMinHashLSHIndex:
    """Maintains an LSH index for cross-document near-duplicate detection across a workspace.

    Enables rapid sub-millisecond retrieval of duplicate or near-identical text passages
    with Jaccard similarity above threshold.
    """

    def __init__(self, threshold: float = 0.85, num_perm: int = 128):
        from datasketch import MinHashLSH

        self.threshold = threshold
        self.num_perm = num_perm
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._minhashes: dict[str, MinHash] = {}
        self.tokenizer = re.compile(r"\b\w+\b")

    def create_minhash(self, text: str) -> MinHash:
        m = MinHash(num_perm=self.num_perm)
        for t in self.tokenizer.findall(text.lower()):
            m.update(t.encode("utf-8"))
        return m

    def insert(self, item_id: str, text: str) -> None:
        m = self.create_minhash(text)
        try:
            self.lsh.insert(item_id, m)
            self._minhashes[item_id] = m
        except ValueError:
            # Key already exists in index
            pass

    def query_near_duplicates(self, text: str) -> list[str]:
        """Returns IDs of all chunks having Jaccard similarity >= threshold with query text."""
        m = self.create_minhash(text)
        return self.lsh.query(m)

    def find_cross_document_duplicates(
        self,
        new_chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identifies any new chunk that is a near-duplicate of an existing indexed document."""
        duplicate_matches = []
        for c in new_chunks:
            text = c.get("content", "")
            matches = self.query_near_duplicates(text)
            if matches:
                duplicate_matches.append(
                    {
                        "chunk_index": c.get("chunk_index"),
                        "matched_existing_chunk_ids": matches,
                        "similarity_threshold": self.threshold,
                    }
                )
        return duplicate_matches
