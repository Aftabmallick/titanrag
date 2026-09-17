from contextlib import asynccontextmanager
import os
import time
from typing import Any
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


class LLMOpsSpan:
    def __init__(self, name: str, parent_trace_id: str, metadata: dict[str, Any] | None = None):
        self.name = name
        self.trace_id = parent_trace_id
        self.span_id = str(uuid4())
        self.metadata = metadata or {}
        self.start_time = 0.0
        self.end_time = 0.0
        self.duration_ms = 0.0

    def set_output(self, output: Any) -> None:
        self.metadata["output"] = output

    def record_scores(self, scores: dict[str, float]) -> None:
        self.metadata["scores"] = scores


class LLMOpsTrace:
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

    @asynccontextmanager
    async def span(self, name: str, metadata: dict[str, Any] | None = None):
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
    ):
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

    def get_ui_url(self) -> str:
        base_url = os.getenv("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")
        return f"{base_url}/project/default/traces/{self.trace_id}"


class LLMOpsTracer:
    @staticmethod
    @asynccontextmanager
    async def trace_query(
        workspace_id: UUID,
        query: str,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        tags: list[str] | None = None,
    ):
        trace = LLMOpsTrace(
            workspace_id=workspace_id,
            user_id=user_id,
            query=query,
            session_id=session_id,
            tags=tags,
        )
        try:
            yield trace
        finally:
            trace.end_time = time.time()
            duration_ms = round((trace.end_time - trace.start_time) * 1000.0, 2)
            logger.info(
                "llmops_query_traced",
                trace_id=trace.trace_id,
                workspace_id=str(workspace_id),
                duration_ms=duration_ms,
                spans_count=len(trace.spans),
                trace_url=trace.get_ui_url(),
            )


llmops_tracer = LLMOpsTracer()
