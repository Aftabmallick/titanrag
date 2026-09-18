from typing import Any


class TitanRAGError(Exception):
    """Base exception for all TitanRAG SDK operations."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"[Status {self.status_code}]")
        if self.request_id:
            parts.append(f"[ReqId: {self.request_id}]")
        return " ".join(parts)


class AuthenticationError(TitanRAGError):
    """Raised when API key or JWT credentials are missing, invalid, or expired (HTTP 401)."""

    pass


class PermissionDeniedError(TitanRAGError):
    """Raised when tenant/user lacks permissions for the requested resource (HTTP 403)."""

    pass


class NotFoundError(TitanRAGError):
    """Raised when a workspace, document, or plugin is not found (HTTP 404)."""

    pass


class ConflictError(TitanRAGError):
    """Raised when an object with duplicate slug, name, or hash already exists (HTTP 409)."""

    pass


class RateLimitError(TitanRAGError):
    """Raised when rate limits or Compute Unit spending caps are exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str,
        status_code: int = 429,
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message, status_code=status_code, details=details)
        self.retry_after = retry_after


class ServerError(TitanRAGError):
    """Raised when the TitanRAG server returns a 5xx internal error."""

    pass


def raise_for_status_code(status_code: int, message: str, details: dict[str, Any] | None = None) -> None:
    """Helper to map HTTP status codes to specific TitanRAG exceptions."""
    if status_code == 401:
        raise AuthenticationError(message, status_code, details)
    elif status_code == 403:
        raise PermissionDeniedError(message, status_code, details)
    elif status_code == 404:
        raise NotFoundError(message, status_code, details)
    elif status_code == 409:
        raise ConflictError(message, status_code, details)
    elif status_code == 429:
        raise RateLimitError(message, status_code, details)
    elif status_code >= 500:
        raise ServerError(message, status_code, details)
    else:
        raise TitanRAGError(message, status_code, details)
