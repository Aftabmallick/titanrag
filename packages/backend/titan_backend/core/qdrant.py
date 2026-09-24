"""Qdrant client compatibility module forwarding to titan_backend.clients.qdrant_client."""

from qdrant_client import AsyncQdrantClient, QdrantClient

from titan_backend.clients.qdrant_client import check_qdrant_health, get_qdrant_client
from titan_backend.core.config import settings


def get_qdrant_client_sync() -> QdrantClient:
    """Return a synchronous QdrantClient instance."""
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=10,
    )


__all__ = [
    "AsyncQdrantClient",
    "QdrantClient",
    "check_qdrant_health",
    "get_qdrant_client",
    "get_qdrant_client_sync",
]
