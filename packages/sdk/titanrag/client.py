"""Backwards compatibility shim for titanrag.client."""
from titanrag.async_client import AsyncTitanClient
from titanrag.exceptions import TitanRAGError
from titanrag.sync_client import TitanClient

# Alias TitanRAGClient to AsyncTitanClient for async context manager backwards compatibility
TitanRAGClient = AsyncTitanClient

__all__ = ["TitanClient", "AsyncTitanClient", "TitanRAGClient", "TitanRAGError"]
