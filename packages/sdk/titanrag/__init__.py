"""Official Python SDK and CLI for the TitanRAG Enterprise Platform."""

from titanrag.async_client import AsyncTitanClient
from titanrag.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    TitanRAGError,
)
from titanrag.models import (
    ChatEvent,
    ChatResponse,
    Citation,
    CitationEvent,
    CitationVerifiedEvent,
    Document,
    DocumentUploadResponse,
    DoneEvent,
    ErrorEvent,
    PluginConfig,
    RAGSettingsConfig,
    StatusEvent,
    TokenEvent,
    Workspace,
)
from titanrag.sync_client import TitanClient

__version__ = "0.1.0"

__all__ = [
    "TitanClient",
    "AsyncTitanClient",
    "TitanRAGError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ServerError",
    "Workspace",
    "Document",
    "DocumentUploadResponse",
    "Citation",
    "ChatResponse",
    "ChatEvent",
    "StatusEvent",
    "TokenEvent",
    "CitationEvent",
    "CitationVerifiedEvent",
    "DoneEvent",
    "ErrorEvent",
    "RAGSettingsConfig",
    "PluginConfig",
]
