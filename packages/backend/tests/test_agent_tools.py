import pytest
from titan_backend.services.chat.tools import tool_registry


@pytest.mark.asyncio
async def test_agent_tools_registration():
    tools = tool_registry.get_litellm_tools()
    assert len(tools) == 4
    tool_names = [t["function"]["name"] for t in tools]
    assert "search_workspace_documents" in tool_names
    assert "lookup_knowledge_graph" in tool_names
    assert "get_document_metadata" in tool_names
    assert "calculate_metric" in tool_names


@pytest.mark.asyncio
async def test_agent_tool_execution_math():
    res = await tool_registry.execute_tool("calculate_metric", {"expression": "(100 * 5) / 2 + 10"})
    assert res["status"] == "success"
    assert res["result"] == 260.0

    err_res = await tool_registry.execute_tool("calculate_metric", {"expression": "__import__('os').system('ls')"})
    assert err_res["status"] == "error"


@pytest.mark.asyncio
async def test_agent_tool_execution_docs():
    res = await tool_registry.execute_tool("search_workspace_documents", {"query": "authentication"})
    assert res["status"] == "success"
    assert len(res["results"]) > 0
    assert "authentication" in res["results"][0]["snippet"]


@pytest.mark.asyncio
async def test_agent_tool_execution_kg():
    res = await tool_registry.execute_tool("lookup_knowledge_graph", {"entity_name": "TitanRAG"})
    assert res["status"] == "success"
    assert res["entity"] == "TitanRAG"
    assert len(res["relations"]) >= 1
