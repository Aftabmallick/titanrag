import os
import time
from collections.abc import Generator
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
from titanrag.streaming import iter_sse_events


class TitanClient:
    """
    Official Synchronous Python Client for the TitanRAG Enterprise Platform.
    Provides context-managed interactions, automatic retries with backoff,
    and typed model serialization across all TitanRAG APIs.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
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
        self.max_retries = max_retries

        self._headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "TitanRAG-Python-SDK/0.1.0",
        }
        if self.api_key:
            self._headers["X-API-Key"] = self.api_key
        elif self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"

        self._client: httpx.Client | None = None

        # Bind sub-resources
        self.workspaces = _WorkspacesResource(self)
        self.documents = _DocumentsResource(self)
        self.chat = _ChatResource(self)
        self.settings = _SettingsResource(self)
        self.plugins = _PluginsResource(self)

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=self._headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    def __enter__(self) -> "TitanClient":
        self._get_client()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()
            self._client = None

    def request(
        self,
        method: str,
        path: str,
        is_v1: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        client = self._get_client()
        base = self.api_v1_url if is_v1 else self.root_url
        url = f"{base}/{path.lstrip('/')}"

        req_headers = dict(self._headers)
        if headers:
            req_headers.update(headers)

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = client.request(method, url, headers=req_headers, **kwargs)
                if resp.is_error:
                    if resp.status_code in (429, 503, 504) and attempt < self.max_retries:
                        time.sleep(0.5 * (2**attempt))
                        continue
                    try:
                        err_body = resp.json().get("error", {})
                        msg = err_body.get("message", resp.text)
                    except Exception:
                        msg = resp.text
                    raise_for_status_code(resp.status_code, msg)
                return resp
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise TitanRAGError(f"Connection failed to {url}: {exc}") from exc

        raise TitanRAGError(f"Request failed after {self.max_retries} retries: {last_exc}")

    # Top-level helper methods
    def query(
        self,
        query: str,
        workspace_id: UUID | str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> ChatResponse:
        return self.chat.ask(
            workspace_id=workspace_id,
            query=query,
            session_id=session_id,
            grounding_mode=grounding_mode,
        )

    def chat_stream(
        self,
        query: str,
        workspace_id: UUID | str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> Generator[ChatEvent, None, None]:
        return self.chat.stream(
            workspace_id=workspace_id,
            query=query,
            session_id=session_id,
            grounding_mode=grounding_mode,
        )

    def upload(
        self,
        workspace_id: UUID | str,
        file_path_or_bytes: str | Path | bytes,
        filename: str | None = None,
        acl_groups: list[str] | None = None,
    ) -> DocumentUploadResponse:
        return self.documents.upload(
            workspace_id=workspace_id,
            file_path_or_bytes=file_path_or_bytes,
            filename=filename,
            acl_groups=acl_groups,
        )


class _WorkspacesResource:
    def __init__(self, client: TitanClient):
        self._c = client

    def list(self) -> list[Workspace]:
        resp = self._c.request("GET", "/workspaces")
        items = resp.json()
        return [Workspace.model_validate(w) for w in items]

    def create(self, name: str, description: str | None = None) -> Workspace:
        resp = self._c.request("POST", "/workspaces", json={"name": name, "description": description})
        return Workspace.model_validate(resp.json())

    def get(self, workspace_id: UUID | str) -> Workspace:
        resp = self._c.request("GET", f"/workspaces/{workspace_id}")
        return Workspace.model_validate(resp.json())


class _DocumentsResource:
    def __init__(self, client: TitanClient):
        self._c = client

    def list(self, workspace_id: UUID | str) -> list[Document]:
        resp = self._c.request("GET", f"/workspaces/{workspace_id}/documents")
        items = resp.json()
        return [Document.model_validate(d) for d in items]

    def upload(
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

        resp = self._c.request("POST", f"/workspaces/{workspace_id}/documents/upload", files=files, data=data)
        return DocumentUploadResponse.model_validate(resp.json())

    def get_status(self, workspace_id: UUID | str, document_id: UUID | str) -> Document:
        resp = self._c.request("GET", f"/workspaces/{workspace_id}/documents/{document_id}")
        return Document.model_validate(resp.json())

    def reindex(self, workspace_id: UUID | str, document_id: UUID | str) -> None:
        self._c.request("POST", f"/workspaces/{workspace_id}/documents/{document_id}/reindex")

    def delete(self, workspace_id: UUID | str, document_id: UUID | str) -> None:
        self._c.request("DELETE", f"/workspaces/{workspace_id}/documents/{document_id}")


class _ChatResource:
    def __init__(self, client: TitanClient):
        self._c = client

    def ask(
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

        resp = self._c.request("POST", f"/workspaces/{workspace_id}/chat", json=payload)
        return ChatResponse.model_validate(resp.json())

    def stream(
        self,
        workspace_id: UUID | str,
        query: str,
        session_id: UUID | str | None = None,
        grounding_mode: str = "Balanced",
    ) -> Generator[ChatEvent, None, None]:
        payload = {
            "query": query,
            "grounding_mode": grounding_mode,
        }
        if session_id:
            payload["session_id"] = str(session_id)

        client = self._c._get_client()
        url = f"{self._c.api_v1_url}/workspaces/{workspace_id}/chat/stream"

        with client.stream("POST", url, json=payload, headers={"Accept": "text/event-stream"}) as response:
            if response.is_error:
                raise_for_status_code(response.status_code, response.read().decode())
            yield from iter_sse_events(response.iter_lines())


class _SettingsResource:
    def __init__(self, client: TitanClient):
        self._c = client

    def get(self, workspace_id: UUID | str) -> RAGSettingsConfig:
        resp = self._c.request("GET", f"/workspaces/{workspace_id}/settings")
        return RAGSettingsConfig.model_validate(resp.json())

    def update(self, workspace_id: UUID | str, **kwargs: Any) -> RAGSettingsConfig:
        resp = self._c.request("PUT", f"/workspaces/{workspace_id}/settings", json=kwargs)
        return RAGSettingsConfig.model_validate(resp.json())


class _PluginsResource:
    def __init__(self, client: TitanClient):
        self._c = client

    def list(self, workspace_id: UUID | str) -> list[PluginConfig]:
        resp = self._c.request("GET", f"/workspaces/{workspace_id}/plugins")
        items = resp.json()
        return [PluginConfig.model_validate(p) for p in items]

    def register(
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
        resp = self._c.request("POST", f"/workspaces/{workspace_id}/plugins", json=payload)
        return resp.json()

    def ping(self, workspace_id: UUID | str, plugin_id: UUID | str) -> dict[str, Any]:
        resp = self._c.request("POST", f"/workspaces/{workspace_id}/plugins/{plugin_id}/ping")
        return resp.json()

    def delete(self, workspace_id: UUID | str, plugin_id: UUID | str) -> None:
        self._c.request("DELETE", f"/workspaces/{workspace_id}/plugins/{plugin_id}")
