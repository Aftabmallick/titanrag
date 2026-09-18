import json
from collections.abc import AsyncGenerator, Generator
from typing import Any

from titanrag.models import (
    ChatEvent,
    Citation,
    CitationEvent,
    CitationVerifiedEvent,
    DoneEvent,
    ErrorEvent,
    StatusEvent,
    TokenEvent,
)


def parse_sse_line(line: str) -> dict[str, Any] | None:
    """Parse a single SSE line (e.g. 'data: {"type": "token", "token": "..."}')."""
    stripped = line.strip()
    if not stripped or stripped.startswith(":") or stripped == "data: [DONE]":
        return None

    if stripped.startswith("data:"):
        payload_str = stripped[5:].strip()
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError:
            return {"type": "token", "token": payload_str}
    return None


def construct_chat_event(data: dict[str, Any], token_index: int = 0) -> ChatEvent | None:
    """Convert parsed SSE JSON payload into a strongly-typed ChatEvent variant."""
    event_type = data.get("type", "token")

    if event_type == "status" or "status" in data:
        return StatusEvent(
            status=data.get("status", "processing"),
            message=data.get("message", ""),
        )
    elif event_type == "token":
        return TokenEvent(
            token=data.get("token", data.get("content", "")),
            index=token_index,
        )
    elif event_type == "citation":
        raw_cite = data.get("citation", data)
        return CitationEvent(
            citation=Citation(
                citation_id=raw_cite.get("id") or raw_cite.get("citation_id"),
                document_id=raw_cite.get("document_id", ""),
                filename=raw_cite.get("filename") or raw_cite.get("document_name"),
                page=raw_cite.get("page", 1),
                snippet=raw_cite.get("snippet") or raw_cite.get("text", ""),
                relevance_score=raw_cite.get("relevance_score") or raw_cite.get("score"),
            )
        )
    elif event_type == "citation_verified":
        return CitationVerifiedEvent(
            citation_id=data.get("citation_id", ""),
            verified=data.get("verified", True),
            nli_score=data.get("nli_score", 1.0),
        )
    elif event_type == "done":
        return DoneEvent(
            session_id=data.get("session_id"),
            full_answer=data.get("full_answer", data.get("answer", "")),
            follow_up_questions=data.get("follow_up_questions", []),
        )
    elif event_type == "error":
        return ErrorEvent(
            error=data.get("error", "Unknown streaming error"),
            code=data.get("code"),
        )
    return None


def iter_sse_events(lines: Generator[str, None, None]) -> Generator[ChatEvent, None, None]:
    """Synchronous generator yielding typed ChatEvents from an SSE text line iterator."""
    token_idx = 0
    for line in lines:
        payload = parse_sse_line(line)
        if payload:
            event = construct_chat_event(payload, token_index=token_idx)
            if event:
                if isinstance(event, TokenEvent):
                    token_idx += 1
                yield event


async def aiter_sse_events(lines: AsyncGenerator[str, None]) -> AsyncGenerator[ChatEvent, None]:
    """Asynchronous generator yielding typed ChatEvents from an SSE text line stream."""
    token_idx = 0
    async for line in lines:
        payload = parse_sse_line(line)
        if payload:
            event = construct_chat_event(payload, token_index=token_idx)
            if event:
                if isinstance(event, TokenEvent):
                    token_idx += 1
                yield event
