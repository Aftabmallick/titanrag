import json
from uuid import uuid4

import httpx
import pytest
from titanrag import AsyncTitanClient, TitanClient
from titanrag.exceptions import AuthenticationError
from titanrag.models import CitationEvent, DoneEvent, TokenEvent


def mock_sdk_backend(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    auth = request.headers.get("X-API-Key")
    if auth == "invalid_key":
        return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}})

    # Workspaces
    if url.endswith("/api/v1/workspaces") and request.method == "GET":
        return httpx.Response(
            200,
            json=[{
                "id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "name": "Engineering Workspace",
                "slug": "engineering",
                "description": "Tech docs",
                "created_at": "2026-09-18T10:00:00Z",
            }],
        )
    elif url.endswith("/api/v1/workspaces") and request.method == "POST":
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "name": body["name"],
                "slug": "new-ws",
                "description": body.get("description"),
            },
        )

    # Documents
    elif "/documents/upload" in url:
        return httpx.Response(
            200,
            json={
                "document_id": str(uuid4()),
                "filename": "handbook.pdf",
                "status": "PROCESSING",
                "message": "Uploaded",
            },
        )
    elif "/documents" in url and request.method == "GET":
        return httpx.Response(
            200,
            json=[{
                "id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "workspace_id": str(uuid4()),
                "filename": "handbook.pdf",
                "status": "READY",
                "chunk_count": 42,
                "file_size_bytes": 1048576,
            }],
        )

    # Chat non-stream
    elif url.endswith("/chat") and request.method == "POST":
        return httpx.Response(
            200,
            json={
                "session_id": str(uuid4()),
                "answer": "TitanRAG provides high-performance vector retrieval.",
                "citations": [{
                    "citation_id": "cite-1",
                    "document_id": str(uuid4()),
                    "filename": "handbook.pdf",
                    "page": 3,
                    "snippet": "TitanRAG provides high-performance vector retrieval.",
                    "relevance_score": 0.95,
                }],
                "follow_up_questions": ["What vector database is used?"],
            },
        )

    # Chat SSE stream
    elif "/chat/stream" in url and request.method == "POST":
        sse_lines = [
            'data: {"type": "status", "status": "searching", "message": "Searching knowledge base..."}\n\n',
            'data: {"type": "token", "token": "TitanRAG "}\n\n',
            'data: {"type": "token", "token": "is "}\n\n',
            'data: {"type": "token", "token": "fast."}\n\n',
            'data: {"type": "citation", "citation": {"id": "c1", "document_id": "d1", "filename": "doc.pdf", "page": 1, "snippet": "fast retrieval"}}\n\n',
            'data: {"type": "done", "full_answer": "TitanRAG is fast.", "follow_up_questions": ["How fast?"]}\n\n',
            "data: [DONE]\n\n",
        ]
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content="".join(sse_lines).encode("utf-8"),
        )

    # Settings
    elif "/settings" in url and request.method == "GET":
        return httpx.Response(
            200,
            json={
                "retrieval_mode": "HYBRID",
                "dense_weight": 0.7,
                "sparse_weight": 0.3,
                "top_k": 20,
                "rerank_top_k": 5,
                "score_threshold": 0.4,
                "hyde_enabled": False,
                "semantic_cache_enabled": True,
            },
        )
    elif "/settings" in url and request.method == "PUT":
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "retrieval_mode": body.get("retrieval_mode", "HYBRID"),
                "dense_weight": body.get("dense_weight", 0.7),
                "sparse_weight": body.get("sparse_weight", 0.3),
                "top_k": body.get("top_k", 20),
                "rerank_top_k": body.get("rerank_top_k", 5),
                "score_threshold": 0.4,
                "hyde_enabled": False,
                "semantic_cache_enabled": True,
            },
        )

    # 404 fallback
    return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "Resource not found"}})


def test_sync_client_workspaces_and_chat():
    transport = httpx.MockTransport(mock_sdk_backend)
    client = TitanClient(base_url="http://testserver", api_key="tr_valid_key")
    client._client = httpx.Client(transport=transport, headers=client._headers)

    # Workspaces
    ws_list = client.workspaces.list()
    assert len(ws_list) == 1
    assert ws_list[0].name == "Engineering Workspace"

    ws_new = client.workspaces.create("New Project", "Desc")
    assert ws_new.name == "New Project"

    # Chat ask
    ws_id = ws_list[0].id
    resp = client.query("What is TitanRAG?", workspace_id=ws_id)
    assert "high-performance" in resp.answer
    assert len(resp.citations) == 1
    assert resp.citations[0].filename == "handbook.pdf"


def test_sync_client_sse_streaming():
    transport = httpx.MockTransport(mock_sdk_backend)
    client = TitanClient(base_url="http://testserver", api_key="tr_valid_key")
    client._client = httpx.Client(transport=transport, headers=client._headers)

    ws_id = str(uuid4())
    events = list(client.chat_stream("How fast is TitanRAG?", workspace_id=ws_id))

    token_events = [e for e in events if isinstance(e, TokenEvent)]
    citation_events = [e for e in events if isinstance(e, CitationEvent)]
    done_events = [e for e in events if isinstance(e, DoneEvent)]

    assert len(token_events) == 3
    tokens_text = "".join(t.token for t in token_events)
    assert tokens_text == "TitanRAG is fast."

    assert len(citation_events) == 1
    assert citation_events[0].citation.filename == "doc.pdf"

    assert len(done_events) == 1
    assert done_events[0].full_answer == "TitanRAG is fast."


def test_sync_client_error_handling():
    transport = httpx.MockTransport(mock_sdk_backend)
    client = TitanClient(base_url="http://testserver", api_key="invalid_key")
    client._client = httpx.Client(transport=transport, headers=client._headers)

    with pytest.raises(AuthenticationError):
        client.workspaces.list()


@pytest.mark.asyncio
async def test_async_client_workspaces_and_streaming():
    transport = httpx.MockTransport(mock_sdk_backend)
    client = AsyncTitanClient(base_url="http://testserver", api_key="tr_valid_key")
    client._client = httpx.AsyncClient(transport=transport, headers=client._headers)

    ws_list = await client.workspaces.list()
    assert len(ws_list) == 1

    ws_id = ws_list[0].id
    accumulated = ""
    async for event in client.chat_stream("Query", workspace_id=ws_id):
        if isinstance(event, TokenEvent):
            accumulated += event.token

    assert accumulated == "TitanRAG is fast."
