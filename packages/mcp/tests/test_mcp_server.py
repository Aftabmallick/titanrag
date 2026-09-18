from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from titan_mcp.server import create_mcp_server
from titanrag.models import ChatResponse, Citation, Document, Workspace


@pytest.fixture
def mock_client():
    client = MagicMock()
    ws = Workspace(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Engineering Docs",
        slug="eng-docs",
    )
    client.workspaces.list.return_value = [ws]
    client.workspaces.get.return_value = ws

    doc = Document(
        id=uuid4(),
        tenant_id=uuid4(),
        workspace_id=ws.id,
        filename="architecture.pdf",
        status="READY",
        chunk_count=12,
    )
    client.documents.list.return_value = [doc]
    client.documents.get_status.return_value = doc

    client.query.return_value = ChatResponse(
        answer="TitanRAG uses dense and sparse retrieval.",
        citations=[
            Citation(
                citation_id="c1", document_id=str(doc.id), filename="architecture.pdf", snippet="Dense + BM25", page=1
            )
        ],
    )
    return client


@pytest.mark.asyncio
async def test_mcp_server_tools_registered(mock_client):
    server = create_mcp_server(client=mock_client)
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert "ask_question" in tool_names
    assert "search_documents" in tool_names
    assert "list_workspaces" in tool_names
    assert "list_documents" in tool_names
    assert "get_document_content" in tool_names


@pytest.mark.asyncio
async def test_mcp_server_call_ask_question(mock_client):
    server = create_mcp_server(client=mock_client)
    res = await server.call_tool("ask_question", {"query": "What is TitanRAG?", "workspace_id": "test-ws-id"})

    # Result contains contents
    assert res is not None
    text_content = str(res)
    assert "TitanRAG uses dense and sparse retrieval" in text_content
    assert "architecture.pdf" in text_content


@pytest.mark.asyncio
async def test_mcp_server_call_list_workspaces(mock_client):
    server = create_mcp_server(client=mock_client)
    res = await server.call_tool("list_workspaces", {})

    assert res is not None
    text_content = str(res)
    assert "Engineering Docs" in text_content


@pytest.mark.asyncio
async def test_mcp_server_prompts(mock_client):
    server = create_mcp_server(client=mock_client)
    prompts = await server.list_prompts()
    prompt_names = [p.name for p in prompts]
    assert "titan_synthesis_prompt" in prompt_names
