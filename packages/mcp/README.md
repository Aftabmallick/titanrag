# TitanRAG Model Context Protocol (MCP) Server

Official MCP Server exposing TitanRAG workspaces, retrieval engines, and documents to AI agents, Claude Desktop, Cursor, and Antigravity.

## Installation

```bash
pip install titan-mcp
# or using uv
uv tool install titan-mcp
```

## Running the Server

### stdio Transport (For Claude Desktop & Cursor)
```bash
export TITANRAG_API_KEY="tr_your_key"
export TITANRAG_BASE_URL="http://localhost:8000"
titan-mcp --transport stdio
```

### SSE Transport (For remote AI swarms)
```bash
titan-mcp --transport sse --port 8080
```

## Claude Desktop Configuration (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "titanrag": {
      "command": "titan-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "TITANRAG_API_KEY": "tr_your_api_key_here",
        "TITANRAG_BASE_URL": "https://api.titanrag.io"
      }
    }
  }
}
```

## Available MCP Tools

- `search_documents(query, workspace_id, top_k, alpha)`: Semantic hybrid retrieval returning chunks and citations.
- `ask_question(query, workspace_id, grounding_mode)`: End-to-end RAG question answering with verified citations.
- `list_workspaces()`: List accessible workspaces in the tenant.
- `list_documents(workspace_id)`: List documents and ingestion status.
- `get_document_content(document_id, workspace_id)`: Retrieve full document content and chunk breakdown.

## Available Resources

- `workspace://{workspace_id}`: Live workspace summary and configuration.
- `document://{document_id}`: Document content and metadata.
- `config://rag-settings/{workspace_id}`: Active RAG settings for the workspace.
