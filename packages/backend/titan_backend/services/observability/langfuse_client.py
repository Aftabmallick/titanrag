"""LLM Observability Provider — Dual-backend support for Langfuse and Arize Phoenix.

Users select their preferred backend via LLMOPS_PROVIDER env var:
- "langfuse" (default): traces to Langfuse (Docker self-hosted or cloud-hosted)
- "phoenix": traces to Arize Phoenix (Docker self-hosted or cloud-hosted)
- "none": disables external tracing (structlog fallback only)

Both providers emit structured logs to structlog as a universal fallback.
"""

import os
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Span / Trace data classes
# ---------------------------------------------------------------------------
class LLMOpsSpan:
    """Represents a single span (retrieval, reranking, embedding, etc.) within a trace."""

    def __init__(self, name: str, parent_trace_id: str, metadata: dict[str, Any] | None = None):
        self.name = name
        self.trace_id = parent_trace_id
        self.span_id = str(uuid4())
        self.metadata = metadata or {}
        self.start_time = 0.0
        self.end_time = 0.0
        self.duration_ms = 0.0
        self._external_span: Any = None  # Provider-specific span object

    def set_output(self, output: Any) -> None:
        self.metadata["output"] = output

    def record_scores(self, scores: dict[str, float]) -> None:
        self.metadata["scores"] = scores

    def set_usage(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0) -> None:
        self.metadata["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
        }


class LLMOpsTrace:
    """Represents a full query-to-response trace with nested spans."""

    def __init__(
        self,
        workspace_id: UUID,
        user_id: UUID | None,
        query: str,
        session_id: UUID | None = None,
        tags: list[str] | None = None,
    ):
        self.trace_id = str(uuid4())
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.session_id = session_id
        self.query = query
        self.tags = tags or []
        self.spans: list[LLMOpsSpan] = []
        self.start_time = time.time()
        self.end_time = 0.0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self._external_trace: Any = None  # Provider-specific trace object

    @asynccontextmanager
    async def span(self, name: str, metadata: dict[str, Any] | None = None) -> AsyncIterator[LLMOpsSpan]:
        s = LLMOpsSpan(name=name, parent_trace_id=self.trace_id, metadata=metadata)
        s.start_time = time.time()
        self.spans.append(s)
        try:
            yield s
        finally:
            s.end_time = time.time()
            s.duration_ms = round((s.end_time - s.start_time) * 1000.0, 2)
            s.metadata["duration_ms"] = s.duration_ms

    @asynccontextmanager
    async def generation(
        self,
        name: str,
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMOpsSpan]:
        s = LLMOpsSpan(name=name, parent_trace_id=self.trace_id, metadata=metadata)
        s.metadata["model"] = model
        s.start_time = time.time()
        self.spans.append(s)
        try:
            yield s
        finally:
            s.end_time = time.time()
            s.duration_ms = round((s.end_time - s.start_time) * 1000.0, 2)
            s.metadata["duration_ms"] = s.duration_ms


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------
class LLMOpsProvider(ABC):
    """Abstract interface for LLM observability backends."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the provider connection."""
        ...

    @abstractmethod
    def create_trace(self, trace: LLMOpsTrace) -> None:
        """Register a new trace with the external provider."""
        ...

    @abstractmethod
    def finalize_trace(self, trace: LLMOpsTrace) -> None:
        """Flush / finalize the trace after query completion."""
        ...

    @abstractmethod
    def record_span(self, trace: LLMOpsTrace, span: LLMOpsSpan) -> None:
        """Record a completed span within a trace."""
        ...

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered data to the backend."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Graceful shutdown (flush + close connections)."""
        ...

    @abstractmethod
    def get_trace_url(self, trace: LLMOpsTrace) -> str:
        """Return a deep-link URL to view this trace in the provider's UI."""
        ...


# ---------------------------------------------------------------------------
# Langfuse Provider
# ---------------------------------------------------------------------------
class LangfuseProvider(LLMOpsProvider):
    """Langfuse integration — supports both self-hosted (Docker) and cloud-hosted instances."""

    def __init__(self) -> None:
        self._client: Any = None
        self._enabled = False

    def initialize(self) -> None:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        host = os.getenv(
            "LANGFUSE_HOST", "http://localhost:3002" if not os.path.exists("/.dockerenv") else "http://langfuse:3000"
        )

        if not secret_key or not public_key:
            logger.info("langfuse_disabled_no_keys", hint="Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY to enable")
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                secret_key=secret_key,
                public_key=public_key,
                host=host,
            )
            self._enabled = True
            logger.info("langfuse_provider_initialized", host=host)
        except ImportError:
            logger.warning("langfuse_sdk_not_installed", hint="pip install langfuse")
        except Exception as e:
            logger.error("langfuse_init_failed", error=str(e))

    def create_trace(self, trace: LLMOpsTrace) -> None:
        if not self._enabled or not self._client:
            return
        try:
            trace._external_trace = self._client.trace(
                id=trace.trace_id,
                name="rag_query",
                user_id=str(trace.user_id) if trace.user_id else None,
                session_id=str(trace.session_id) if trace.session_id else None,
                tags=trace.tags + [f"workspace:{trace.workspace_id}"],
                input=trace.query,
                metadata={"workspace_id": str(trace.workspace_id)},
            )
        except Exception as e:
            logger.warning("langfuse_create_trace_failed", error=str(e))

    def finalize_trace(self, trace: LLMOpsTrace) -> None:
        if not self._enabled or not trace._external_trace:
            return
        try:
            trace._external_trace.update(
                output=f"{len(trace.spans)} spans completed",
                metadata={
                    "total_tokens": trace.total_tokens,
                    "total_cost_usd": trace.total_cost_usd,
                    "duration_ms": round((trace.end_time - trace.start_time) * 1000.0, 2),
                },
            )
        except Exception as e:
            logger.warning("langfuse_finalize_trace_failed", error=str(e))

    def record_span(self, trace: LLMOpsTrace, span: LLMOpsSpan) -> None:
        if not self._enabled or not trace._external_trace:
            return
        try:
            model = span.metadata.get("model")
            if model:
                # This is an LLM generation span
                usage = span.metadata.get("usage", {})
                trace._external_trace.generation(
                    name=span.name,
                    model=model,
                    input=span.metadata.get("input"),
                    output=span.metadata.get("output"),
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    },
                    metadata=span.metadata,
                )
            else:
                # Regular span (retrieval, reranking, etc.)
                trace._external_trace.span(
                    name=span.name,
                    input=span.metadata.get("input"),
                    output=span.metadata.get("output"),
                    metadata=span.metadata,
                )
        except Exception as e:
            logger.warning("langfuse_record_span_failed", span=span.name, error=str(e))

    def flush(self) -> None:
        if self._enabled and self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.warning("langfuse_flush_failed", error=str(e))

    def shutdown(self) -> None:
        if self._enabled and self._client:
            try:
                self._client.flush()
                self._client.shutdown()
                logger.info("langfuse_provider_shutdown")
            except Exception as e:
                logger.warning("langfuse_shutdown_failed", error=str(e))

    def get_trace_url(self, trace: LLMOpsTrace) -> str:
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")
        return f"{host}/project/default/traces/{trace.trace_id}"


# ---------------------------------------------------------------------------
# Arize Phoenix Provider
# ---------------------------------------------------------------------------
class PhoenixProvider(LLMOpsProvider):
    """Arize Phoenix integration — supports both self-hosted (Docker) and cloud-hosted instances."""

    def __init__(self) -> None:
        self._client: Any = None
        self._tracer: Any = None
        self._enabled = False

    def initialize(self) -> None:
        phoenix_host = os.getenv(
            "PHOENIX_HOST", "http://localhost:6006" if not os.path.exists("/.dockerenv") else "http://phoenix:6006"
        )
        phoenix_api_key = os.getenv("PHOENIX_API_KEY")

        try:
            from opentelemetry import trace as otel_trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            # Configure OTel exporter to Phoenix's OTLP endpoint
            collector_endpoint = f"{phoenix_host}/v1/traces"
            headers: dict[str, str] = {}
            if phoenix_api_key:
                headers["Authorization"] = f"Bearer {phoenix_api_key}"

            exporter = OTLPSpanExporter(endpoint=collector_endpoint, headers=headers)
            provider = TracerProvider()
            provider.add_span_processor(SimpleSpanProcessor(exporter))
            otel_trace.set_tracer_provider(provider)

            self._tracer = otel_trace.get_tracer("titanrag.llmops")
            self._enabled = True
            logger.info("phoenix_provider_initialized", host=phoenix_host)
        except ImportError:
            logger.warning(
                "phoenix_otel_sdk_not_installed",
                hint="pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http arize-phoenix",
            )
        except Exception as e:
            logger.error("phoenix_init_failed", error=str(e))

    def create_trace(self, trace: LLMOpsTrace) -> None:
        if not self._enabled or not self._tracer:
            return
        try:
            span = self._tracer.start_span(
                name="rag_query",
                attributes={
                    "trace_id": trace.trace_id,
                    "user_id": str(trace.user_id) if trace.user_id else "",
                    "workspace_id": str(trace.workspace_id),
                    "session_id": str(trace.session_id) if trace.session_id else "",
                    "input.value": trace.query,
                    "openinference.span.kind": "CHAIN",
                },
            )
            trace._external_trace = span
        except Exception as e:
            logger.warning("phoenix_create_trace_failed", error=str(e))

    def finalize_trace(self, trace: LLMOpsTrace) -> None:
        if not self._enabled or not trace._external_trace:
            return
        try:
            ext_span = trace._external_trace
            ext_span.set_attribute("output.value", f"{len(trace.spans)} spans completed")
            ext_span.set_attribute("llm.token_count.total", trace.total_tokens)
            ext_span.end()
        except Exception as e:
            logger.warning("phoenix_finalize_trace_failed", error=str(e))

    def record_span(self, trace: LLMOpsTrace, span: LLMOpsSpan) -> None:
        if not self._enabled or not self._tracer:
            return
        try:
            otel_span = self._tracer.start_span(
                name=span.name,
                attributes={
                    "parent_trace_id": span.trace_id,
                    "duration_ms": span.duration_ms,
                    "openinference.span.kind": "LLM" if span.metadata.get("model") else "RETRIEVER",
                },
            )
            if span.metadata.get("model"):
                otel_span.set_attribute("llm.model_name", span.metadata["model"])
                usage = span.metadata.get("usage", {})
                otel_span.set_attribute("llm.token_count.prompt", usage.get("prompt_tokens", 0))
                otel_span.set_attribute("llm.token_count.completion", usage.get("completion_tokens", 0))
            if span.metadata.get("output"):
                otel_span.set_attribute("output.value", str(span.metadata["output"])[:5000])
            otel_span.end()
        except Exception as e:
            logger.warning("phoenix_record_span_failed", span=span.name, error=str(e))

    def flush(self) -> None:
        pass  # OTel SimpleSpanProcessor exports immediately

    def shutdown(self) -> None:
        if self._enabled:
            try:
                from opentelemetry import trace as otel_trace

                provider = otel_trace.get_tracer_provider()
                if hasattr(provider, "shutdown"):
                    provider.shutdown()
                logger.info("phoenix_provider_shutdown")
            except Exception as e:
                logger.warning("phoenix_shutdown_failed", error=str(e))

    def get_trace_url(self, trace: LLMOpsTrace) -> str:
        host = os.getenv("PHOENIX_HOST", "http://localhost:6006").rstrip("/")
        return f"{host}/traces/{trace.trace_id}"


# ---------------------------------------------------------------------------
# Structlog-Only Fallback Provider (no external dependencies)
# ---------------------------------------------------------------------------
class StructlogFallbackProvider(LLMOpsProvider):
    """Logs all trace data to structlog only — zero external dependencies."""

    def initialize(self) -> None:
        logger.info("llmops_provider_structlog_fallback")

    def create_trace(self, trace: LLMOpsTrace) -> None:
        pass

    def finalize_trace(self, trace: LLMOpsTrace) -> None:
        pass

    def record_span(self, trace: LLMOpsTrace, span: LLMOpsSpan) -> None:
        pass

    def flush(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def get_trace_url(self, trace: LLMOpsTrace) -> str:
        return f"structlog://local/{trace.trace_id}"


# ---------------------------------------------------------------------------
# Factory + Unified Tracer
# ---------------------------------------------------------------------------
def _create_provider() -> LLMOpsProvider:
    """Factory that selects the provider based on LLMOPS_PROVIDER env var."""
    provider_name = os.getenv("LLMOPS_PROVIDER", "phoenix").lower().strip()
    provider: LLMOpsProvider

    if provider_name == "phoenix":
        provider = PhoenixProvider()
    elif provider_name == "langfuse":
        provider = LangfuseProvider()
    elif provider_name == "none":
        provider = StructlogFallbackProvider()
    else:
        logger.warning("unknown_llmops_provider", provider=provider_name, fallback="structlog")
        provider = StructlogFallbackProvider()

    provider.initialize()
    return provider


class LLMOpsTracer:
    """Unified tracer facade that delegates to the configured provider."""

    def __init__(self) -> None:
        self._provider: LLMOpsProvider | None = None

    @property
    def provider(self) -> LLMOpsProvider:
        if self._provider is None:
            self._provider = _create_provider()
        return self._provider

    @asynccontextmanager
    async def trace_query(
        self,
        workspace_id: UUID,
        query: str,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[LLMOpsTrace]:
        trace = LLMOpsTrace(
            workspace_id=workspace_id,
            user_id=user_id,
            query=query,
            session_id=session_id,
            tags=tags,
        )

        # Register trace with external provider
        self.provider.create_trace(trace)

        try:
            yield trace
        finally:
            trace.end_time = time.time()
            duration_ms = round((trace.end_time - trace.start_time) * 1000.0, 2)

            # Record all completed spans
            for span in trace.spans:
                self.provider.record_span(trace, span)

            # Finalize trace
            self.provider.finalize_trace(trace)

            # Always log to structlog as universal fallback
            logger.info(
                "llmops_query_traced",
                trace_id=trace.trace_id,
                workspace_id=str(workspace_id),
                duration_ms=duration_ms,
                spans_count=len(trace.spans),
                total_tokens=trace.total_tokens,
                trace_url=self.provider.get_trace_url(trace),
                provider=type(self.provider).__name__,
            )

    def flush(self) -> None:
        """Flush buffered data to the external provider."""
        self.provider.flush()

    def shutdown(self) -> None:
        """Graceful shutdown — call from application lifespan teardown."""
        self.provider.shutdown()


# Module-level singleton
llmops_tracer = LLMOpsTracer()
