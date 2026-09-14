from types import TracebackType
from typing import Any, Self, cast

import httpx


class TitanRAGError(Exception):
    """Base exception for TitanRAG SDK client."""

    def __init__(self, message: str, status_code: int | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class TitanRAGClient:
    """
    Official Python Client for the TitanRAG Enterprise Platform.
    Provides async and context-managed interactions with the API engine.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        api_key: str | None = None,
        timeout: float = 15.0,
    ):
        self.base_url = base_url.rstrip("/")
        # Derive root server url for unversioned probes (e.g. /health/live, /metrics)
        if self.base_url.endswith("/api/v1"):
            self.root_url = self.base_url[:-7]
        else:
            self.root_url = self.base_url

        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key

        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=self.timeout)
        return self._client

    async def __aenter__(self) -> Self:
        self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_error:
            try:
                error_body = response.json().get("error", {})
                raise TitanRAGError(
                    message=error_body.get("message", response.text),
                    status_code=response.status_code,
                    details=error_body,
                )
            except (ValueError, KeyError):
                raise TitanRAGError(
                    message=f"HTTP {response.status_code}: {response.text}",
                    status_code=response.status_code,
                ) from None
        return cast(dict[str, Any], response.json())

    async def get_health_live(self) -> dict[str, Any]:
        """Query liveness probe."""
        client = self._get_client()
        resp = await client.get(f"{self.root_url}/health/live")
        return await self._handle_response(resp)

    async def get_health_ready(self) -> dict[str, Any]:
        """Query deep readiness probe for all dependencies."""
        client = self._get_client()
        resp = await client.get(f"{self.root_url}/health/ready")
        return await self._handle_response(resp)

    async def get_health(self) -> dict[str, Any]:
        """Alias for get_health_ready."""
        return await self.get_health_ready()

    async def get_metrics(self) -> str:
        """Fetch raw Prometheus metrics text."""
        client = self._get_client()
        resp = await client.get(f"{self.root_url}/metrics")
        if resp.is_error:
            raise TitanRAGError(message=f"Failed to fetch metrics: {resp.text}", status_code=resp.status_code)
        return resp.text
