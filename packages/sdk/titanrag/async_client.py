import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from titanrag.exceptions import TitanRAGError, raise_for_status_code
from titanrag.models import (
    ChatEvent,
    ChatResponse,
    Document,
    DocumentUploadResponse,
    PluginConfig,
    RAGSettingsConfig,
    Workspace,
)
from titanrag.streaming import aiter_sse_events


class AsyncTitanClient:
    """
    Official Asynchronous Python Client for the TitanRAG Enterprise Platform.
    Provides async context-managed interactions, SSE token streaming,
    and typed model serialization.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        raw_url = base_url or os.getenv("TITANRAG_BASE_URL", "http://localhost:8000")
        self.base_url = raw_url.rstrip("/")
        if not self.base_url.endswith("/api/v1"):
            self.api_v1_url = f"{self.base_url}/api/v1"
            self.root_url = self.base_url
        else:
            self.api_v1_url = self.base_url
            self.root_url = self.base_url[:-7]

        self.api_key = api_key or os.getenv("TITANRAG_API_KEY")
        self.token = token or os.getenv("TITANRAG_TOKEN")
        self.timeout = timeout

        self._headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "TitanRAG-AsyncPython-SDK/0.1.0",
        }
        if self.api_key:
            self._headers["X-API-Key"] = self.api_key
        elif self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"

        self._client: httpx.AsyncClient | None = None

        self.workspaces = _AsyncWorkspacesResource(self)
        self.documents = _AsyncDocumentsResource(self)
        self.chat = _AsyncChatResource(self)
        self.settings = _AsyncSettingsResource(self)
        self.plugins = _AsyncPluginsResource(self)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def __aenter__(self) -> "AsyncTitanClient":
        self._get_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        is_v1: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        client = self._get_client()
        if client.base_url and client.base_url.is_absolute_url:
            url = f"/api/v1/{path.lstrip('/')}" if is_v1 else f"/{path.lstrip('/')}"
        else:
            base = self.api_v1_url if is_v1 else self.root_url
            url = f"{base}/{path.lstrip('/')}"

        req_headers = dict(self._headers)
        if headers:
            req_headers.update(headers)

        try:
            resp = await client.request(method, url, headers=req_headers, **kwargs)
            if resp.is_error:
                try:
                    err_body = resp.json().get("error", {})
                    msg = err_body.get("message", resp.text)
                except Exception:
                    err_body = {}
                    msg = resp.text
                raise_for_status_code(resp.status_code, msg, details=err_body)
            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise TitanRAGError(f"Connection failed to {url}: {exc}") from exc

    async def get_health_live(self) -> dict[str, Any]:
        """Query unversioned liveness probe."""
        resp = await self.request("GET", "/health/live", is_v1=False)
        return resp.json()

    async def get_health_ready(self) -> dict[str, Any]:
        """Query unversioned deep readiness probe."""
        resp = await self.request("GET", "/health/ready", is_v1=False)
        return resp.json()

    async def get_metrics(self) -> str:
        """Fetch Prometheus metrics."""
        resp = await self.request("GET", "/metrics", is_v1=False)
        return resp.text

    async def query(
        self,
        query: str,
        workspace_id: UUID | str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> ChatResponse:
        return await self.chat.ask(
            workspace_id=workspace_id,
            query=query,
            session_id=session_id,
            grounding_mode=grounding_mode,
        )

    async def chat_stream(
        self,
        query: str,
        workspace_id: UUID | str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> AsyncGenerator[ChatEvent, None]:
        async for event in self.chat.stream(
            workspace_id=workspace_id,
            query=query,
            session_id=session_id,
            grounding_mode=grounding_mode,
        ):
            yield event


class _AsyncWorkspacesResource:
    def __init__(self, client: AsyncTitanClient):
        self._c = client

    async def list(self) -> list[Workspace]:
        resp = await self._c.request("GET", "/workspaces")
        return [Workspace.model_validate(w) for w in resp.json()]

    async def create(self, name: str, description: str | None = None) -> Workspace:
        resp = await self._c.request("POST", "/workspaces", json={"name": name, "description": description})
        return Workspace.model_validate(resp.json())

    async def get(self, workspace_id: UUID | str) -> Workspace:
        resp = await self._c.request("GET", f"/workspaces/{workspace_id}")
        return Workspace.model_validate(resp.json())


class _AsyncDocumentsResource:
    def __init__(self, client: AsyncTitanClient):
        self._c = client

    async def list(self, workspace_id: UUID | str) -> list[Document]:
        resp = await self._c.request("GET", f"/workspaces/{workspace_id}/documents")
        return [Document.model_validate(d) for d in resp.json()]

    async def upload(
        self,
        workspace_id: UUID | str,
        file_path_or_bytes: str | Path | bytes,
        filename: str | None = None,
        acl_groups: list[str] | None = None,
    ) -> DocumentUploadResponse:
        if isinstance(file_path_or_bytes, (str, Path)):
            path = Path(file_path_or_bytes)
            name = filename or path.name
            with open(path, "rb") as f:
                content = f.read()
        else:
            content = file_path_or_bytes
            name = filename or "document.pdf"

        files = {"file": (name, content, "application/octet-stream")}
        data: dict[str, Any] = {}
        if acl_groups:
            data["acl_groups"] = ",".join(acl_groups)

        resp = await self._c.request("POST", f"/workspaces/{workspace_id}/documents/upload", files=files, data=data)
        return DocumentUploadResponse.model_validate(resp.json())

    async def get_status(self, workspace_id: UUID | str, document_id: UUID | str) -> Document:
        resp = await self._c.request("GET", f"/workspaces/{workspace_id}/documents/{document_id}")
        return Document.model_validate(resp.json())

    async def reindex(self, workspace_id: UUID | str, document_id: UUID | str) -> None:
        await self._c.request("POST", f"/workspaces/{workspace_id}/documents/{document_id}/reindex")

    async def delete(self, workspace_id: UUID | str, document_id: UUID | str) -> None:
        await self._c.request("DELETE", f"/workspaces/{workspace_id}/documents/{document_id}")


class _AsyncChatResource:
    def __init__(self, client: AsyncTitanClient):
        self._c = client

    async def ask(
        self,
        workspace_id: UUID | str,
        query: str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> ChatResponse:
        payload = {
            "query": query,
            "grounding_mode": grounding_mode,
        }
        if session_id:
            payload["session_id"] = str(session_id)

        resp = await self._c.request("POST", f"/workspaces/{workspace_id}/chat", json=payload)
        return ChatResponse.model_validate(resp.json())

    async def stream(
        self,
        workspace_id: UUID | str,
        query: str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> AsyncGenerator[ChatEvent, None]:
        payload = {
            "query": query,
            "grounding_mode": grounding_mode,
        }
        if session_id:
            payload["session_id"] = str(session_id)

        client = self._c._get_client()
        url = f"{self._c.api_v1_url}/workspaces/{workspace_id}/chat/stream"

        async with client.stream("POST", url, json=payload, headers={"Accept": "text/event-stream"}) as response:
            if response.is_error:
                err_text = await response.aread()
                raise_for_status_code(response.status_code, err_text.decode())
            async for event in aiter_sse_events(response.aiter_lines()):
                yield event


class _AsyncSettingsResource:
    def __init__(self, client: AsyncTitanClient):
        self._c = client

    async def get(self, workspace_id: UUID | str) -> RAGSettingsConfig:
        resp = await self._c.request("GET", f"/workspaces/{workspace_id}/settings")
        return RAGSettingsConfig.model_validate(resp.json())

    async def update(self, workspace_id: UUID | str, **kwargs: Any) -> RAGSettingsConfig:
        resp = await self._c.request("PUT", f"/workspaces/{workspace_id}/settings", json=kwargs)
        return RAGSettingsConfig.model_validate(resp.json())


class _AsyncPluginsResource:
    def __init__(self, client: AsyncTitanClient):
        self._c = client

    async def list(self, workspace_id: UUID | str) -> list[PluginConfig]:
        resp = await self._c.request("GET", f"/workspaces/{workspace_id}/plugins")
        return [PluginConfig.model_validate(p) for p in resp.json()]

    async def register(
        self,
        workspace_id: UUID | str,
        name: str,
        endpoint_url: str,
        hooks: list[str],
        timeout_ms: int = 2000,
        is_active: bool = True,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "endpoint_url": endpoint_url,
            "hooks": hooks,
            "timeout_ms": timeout_ms,
            "is_active": is_active,
            "description": description,
        }
        resp = await self._c.request("POST", f"/workspaces/{workspace_id}/plugins", json=payload)
        return resp.json()

    async def ping(self, workspace_id: UUID | str, plugin_id: UUID | str) -> dict[str, Any]:
        resp = await self._c.request("POST", f"/workspaces/{workspace_id}/plugins/{plugin_id}/ping")
        return resp.json()

    async def delete(self, workspace_id: UUID | str, plugin_id: UUID | str) -> None:
        await self._c.request("DELETE", f"/workspaces/{workspace_id}/plugins/{plugin_id}")
