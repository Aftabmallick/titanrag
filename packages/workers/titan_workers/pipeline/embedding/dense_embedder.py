import hashlib
import math
import os

import httpx
import structlog
from titan_backend.core.rate_limiter import ProviderTokenBucketLimiter

logger = structlog.get_logger("titanrag.embedding.dense")

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")


class EmbeddingServiceError(Exception):
    """Raised when dense embedding generation fails in production environments."""

    pass


class DenseEmbedder:
    """Batched Dense Vector Embedder (128 chunks per batch).
    Generates normalized dense embeddings (default dimension: 1536).
    Enforces TPM/RPM limits via ProviderTokenBucketLimiter and dispatches to LiteLLM with strict production failure.
    """

    def __init__(
        self,
        dimension: int = 1536,
        model: str = "text-embedding-3-small",
        provider: str = "openai",
        strict_mode: bool | None = None,
    ):
        self.dimension = dimension
        self.model = model
        self.provider = provider
        if strict_mode is not None:
            self.strict_mode = strict_mode
        else:
            env = os.getenv("ENVIRONMENT", "development").lower()
            strict_flag = os.getenv("STRICT_EMBEDDING_MODE", "false").lower() == "true"
            self.strict_mode = env == "production" or strict_flag

        self.limiter = ProviderTokenBucketLimiter(
            provider=self.provider,
            model=self.model,
            max_rpm=3000,
            max_tpm=1_000_000,
        )

    def _generate_deterministic_embedding(self, text: str) -> list[float]:
        """High-performance deterministic unit-normalized embedding for testing & fallback."""
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
            estimated_tokens = sum(len(t.split()) for t in chunk_slice) * 2

            try:
                await self.limiter.acquire(estimated_tokens=estimated_tokens, wait=False)
            except Exception as e:
                logger.warning("rate_limiter_acquire_skipped", error=str(e))

            vectors: list[list[float]] = []
            upstream_error: str | None = None
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{LITELLM_URL}/embeddings",
                        json={"model": self.model, "input": chunk_slice},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        vectors = [item["embedding"] for item in data.get("data", [])]
                    else:
                        upstream_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as exc:
                upstream_error = str(exc)

            if not vectors or len(vectors) != len(chunk_slice):
                if self.strict_mode:
                    error_msg = f"Failed to generate dense embeddings for {len(chunk_slice)} chunks via {self.model}: {upstream_error or 'upstream unavailable'}"
                    logger.error("strict_dense_embedding_failed", error=error_msg, model=self.model)
                    raise EmbeddingServiceError(error_msg)

                # Dev fallback only
                logger.warning(
                    "dense_embedding_dev_fallback",
                    reason=upstream_error or "upstream unavailable",
                    chunks_count=len(chunk_slice),
                )
                vectors = [self._generate_deterministic_embedding(t) for t in chunk_slice]

            # Validate vector dimensions and integrity
            for v in vectors:
                if len(v) != self.dimension or any(math.isnan(x) for x in v):
                    raise EmbeddingServiceError(
                        f"Invalid embedding dimension or NaN detected: expected {self.dimension}, got {len(v)}"
                    )

            embeddings.extend(vectors)

        return embeddings
