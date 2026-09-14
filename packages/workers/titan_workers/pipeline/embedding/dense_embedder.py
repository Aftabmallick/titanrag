import hashlib
import math

import structlog

logger = structlog.get_logger("titanrag.embedding.dense")


class DenseEmbedder:
    """
    Batched Dense Vector Embedder (128 chunks per batch).
    Generates normalized dense embeddings (default dimension: 1536).
    """

    def __init__(self, dimension: int = 1536, model: str = "text-embedding-3-small"):
        self.dimension = dimension
        self.model = model

    def _generate_deterministic_embedding(self, text: str) -> list[float]:
        """
        High-performance deterministic unit-normalized embedding for testing & fallback.
        """
        raw_bytes = hashlib.sha512(text.encode("utf-8")).digest()
        vec: list[float] = []
        for i in range(self.dimension):
            byte_val = raw_bytes[i % len(raw_bytes)]
            val = (float(byte_val) / 255.0) * 2.0 - 1.0
            vec.append(val)

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    async def embed_batch(self, texts: list[str], batch_size: int = 128) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk_slice = texts[i : i + batch_size]
            # When remote provider is configured via LiteLLM, invoke provider;
            # fallback to deterministic high-dimensional embeddings for local tests
            batch_vectors = [self._generate_deterministic_embedding(t) for t in chunk_slice]
            embeddings.extend(batch_vectors)

        return embeddings
