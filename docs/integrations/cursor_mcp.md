# Cursor IDE & Claude Desktop MCP Integration: TitanRAG

The **TitanRAG Model Context Protocol (MCP)** server allows AI assistants such as **Cursor IDE**, **Claude Desktop**, and Windsurf to seamlessly read, query, and search your organization's internal documentation in real time.

---

## 1. Capabilities Exposed via MCP

| Type | Name | Description |
| :--- | :--- | :--- |
| **Tool** | `ask_question` | Ask conversational questions to any workspace and get synthesized answers with citations |
| **Tool** | `search_documents` | Semantic hybrid search returning text chunks, scores, and metadata |
| **Tool** | `list_workspaces` | Discover accessible enterprise workspaces |
| **Tool** | `list_documents` | List ingested files inside a workspace |
| **Tool** | `get_document_content` | Fetch full parsed document text and chunk breakdowns |
| **Resource** | `workspace://{id}` | Live context URI linking current documents in a workspace |
| **Resource** | `config://default-workspace` | Current active workspace configuration |
| **Prompt** | `titan_synthesis_prompt` | Pre-engineered enterprise grounding prompt |

---

## 2. Cursor IDE Configuration

### Step 1: Open Cursor Settings
Go to **Cursor Settings** -> **Features** -> **MCP Servers** -> **Add New MCP Server**.

### Step 2: Configure `titan-mcp`

- **Name**: `titanrag`
- **Type**: `command` (stdio transport)
- **Command**:
  ```bash
  python -m titan_mcp
  ```
- **Environment Variables**:
  ```env
  TITANRAG_API_KEY=titankey_live_xxxxxxxxxxxxxxxxxxxxxx
  TITANRAG_API_URL=http://localhost:8000
  DEFAULT_WORKSPACE_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890
  ```

Or configure it via `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "titanrag": {
      "command": "/Users/username/.venv/bin/python",
      "args": ["-m", "titan_mcp"],
      "env": {
        "TITANRAG_API_KEY": "titankey_live_xxxxxxxxxxxx",
        "TITANRAG_API_URL": "http://localhost:8000",
        "DEFAULT_WORKSPACE_ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    }
  }
}
```

---

## 3. Claude Desktop Configuration

Edit your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "titanrag": {
      "command": "python",
      "args": [
        "-m",
        "titan_mcp"
      ],
      "env": {
        "TITANRAG_API_KEY": "titankey_live_xxxxxxxxxxxx",
        "TITANRAG_API_URL": "https://api.titanrag.enterprise.com",
        "DEFAULT_WORKSPACE_ID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
      }
    }
  }
}
```

Restart Claude Desktop. You will see a hammer 🔨 icon indicating that `titanrag` tools are connected.

---

## 4. Remote HTTP / SSE Mode (Docker Deployment)

For team-wide shared deployment, run `titan-mcp` with SSE transport:

```bash
docker run -d -p 8001:8001 \
  -e TITANRAG_API_KEY=titankey_live_xxx \
  -e TITANRAG_API_URL=http://backend:8000 \
  titanrag/mcp:latest \
  python -m titan_mcp --transport sse --port 8001
```

Configure clients with SSE URL:

```json
{
  "mcpServers": {
    "titanrag-remote": {
      "url": "http://internal-mcp.company.local:8001/sse"
    }
  }
}
```

---

## 5. Example Prompts in Cursor or Claude

- *"Use TitanRAG to find our API rate limiting architecture and explain how our token bucket works."*
- *"Search our internal engineering handbook for our on-call escalation policy."*
- *"List all documents in the Security Compliance workspace."*
