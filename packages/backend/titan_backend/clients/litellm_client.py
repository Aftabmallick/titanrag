import json
from collections.abc import AsyncGenerator
from typing import Any, cast

import httpx

from titan_backend.core.circuit_breaker import litellm_circuit_breaker
from titan_backend.core.config import settings
from titan_backend.core.errors import AppException
from titan_backend.core.logging import logger


class LiteLLMClientError(AppException):
    def __init__(self, message: str, status_code: int = 502, details: dict | None = None):
        super().__init__(
            status_code=status_code,
            error_code="LITELLM_ERROR",
            message=message,
            details=details or {},
        )


class LiteLLMClient:
    """Async client communicating with the LiteLLM Proxy Gateway."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.LITELLM_URL).rstrip("/")
        self.api_key = api_key or settings.LITELLM_MASTER_KEY
        self.timeout = httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=10.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def acompletion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Execute a non-streaming chat completion."""
        if not litellm_circuit_breaker.can_execute():
            raise LiteLLMClientError(
                "LiteLLM circuit breaker open. Inference temporarily unavailable.", status_code=503
            )

        target_model = model or settings.DEFAULT_CHAT_MODEL
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=self._headers(), json=payload)
                if response.is_error:
                    litellm_circuit_breaker.record_failure()
                    logger.error("litellm_completion_error", status=response.status_code, text=response.text)
                    raise LiteLLMClientError(
                        f"LiteLLM error ({response.status_code}): {response.text}",
                        status_code=response.status_code,
                    )
                litellm_circuit_breaker.record_success()
                return cast(dict[str, Any], response.json())
            except httpx.RequestError as e:
                litellm_circuit_breaker.record_failure()
                logger.error("litellm_request_failed", error=str(e))
                raise LiteLLMClientError(f"Failed to connect to LiteLLM: {e}", status_code=502) from e

    async def astream_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Yields raw SSE token text chunks from LiteLLM stream."""
        if not litellm_circuit_breaker.can_execute():
            raise LiteLLMClientError("LiteLLM circuit breaker open.", status_code=503)

        target_model = model or settings.DEFAULT_CHAT_MODEL
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=10.0)) as client:
            try:
                async with client.stream("POST", url, headers=self._headers(), json=payload) as response:
                    if response.is_error:
                        litellm_circuit_breaker.record_failure()
                        err_body = await response.aread()
                        raise LiteLLMClientError(
                            f"LiteLLM stream error ({response.status_code}): {err_body.decode()}",
                            status_code=response.status_code,
                        )

                    litellm_circuit_breaker.record_success()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(raw_data)
                                choices = chunk_json.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            except httpx.RequestError as e:
                litellm_circuit_breaker.record_failure()
                logger.error("litellm_stream_connection_error", error=str(e))
                raise LiteLLMClientError(f"Connection error during LiteLLM streaming: {e}", status_code=502) from e

    async def aembedding(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate dense embeddings for a batch of texts."""
        if not litellm_circuit_breaker.can_execute():
            raise LiteLLMClientError("LiteLLM circuit breaker open.", status_code=503)

        target_model = model or settings.DEFAULT_EMBEDDING_MODEL
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": target_model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=self._headers(), json=payload)
                if response.is_error:
                    litellm_circuit_breaker.record_failure()
                    raise LiteLLMClientError(f"Embedding failed ({response.status_code}): {response.text}")
                litellm_circuit_breaker.record_success()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
            except httpx.RequestError as e:
                litellm_circuit_breaker.record_failure()
                raise LiteLLMClientError(f"Embedding request failed: {e}") from e


litellm_client = LiteLLMClient()
