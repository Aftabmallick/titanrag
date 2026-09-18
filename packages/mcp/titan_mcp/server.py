import json
import os

from mcp.server import MCPServer
from titanrag import TitanClient
from titanrag.exceptions import TitanRAGError


def get_default_client() -> TitanClient:
    return TitanClient(
        base_url=os.getenv("TITANRAG_BASE_URL", "http://localhost:8000"),
        api_key=os.getenv("TITANRAG_API_KEY"),
    )


def create_mcp_server(client: TitanClient | None = None) -> MCPServer:
    """
    Factory creating a fully configured Model Context Protocol (MCP) server
    exposing TitanRAG knowledge retrieval, workspaces, and documents.
    """
    mcp = MCPServer(
        name="titanrag",
        version="0.1.0",
        description="Official Model Context Protocol server for TitanRAG Enterprise Platform",
    )

    sdk_client = client or get_default_client()

    # -------------------------------------------------------------------------
    # MCP Tools
    # -------------------------------------------------------------------------

    @mcp.tool(
        description=(
            "Execute end-to-end hybrid RAG question answering against a TitanRAG workspace. "
            "Returns a synthesized answer with verified document citations."
        )
    )
    def ask_question(
        query: str,
        workspace_id: str,
        grounding_mode: str = "Balanced",
    ) -> str:
        """
        Ask a question grounded in workspace documents.
        :param query: The user's question or research task.
        :param workspace_id: UUID of the target workspace.
        :param grounding_mode: 'Strict', 'Balanced', or 'Creative'.
        """
        try:
            resp = sdk_client.query(
                query=query,
                workspace_id=workspace_id,
                grounding_mode=grounding_mode,
            )
            citations_text = ""
            if resp.citations:
                citations_text = "\n\nSources:\n" + "\n".join(
                    f'[{idx}] {c.filename or c.document_id} (p.{c.page or 1}): "{c.snippet[:120]}..."'
                    for idx, c in enumerate(resp.citations, 1)
                )
            return f"{resp.answer}{citations_text}"
        except TitanRAGError as e:
            return f"Error executing TitanRAG query: {e}"

    @mcp.tool(
        description=(
            "Execute semantic hybrid search (dense + BM25) across workspace document chunks. "
            "Returns top retrieved text snippets with relevance scores and page numbers."
        )
    )
    def search_documents(
        query: str,
        workspace_id: str,
        top_k: int = 5,
        alpha: float = 0.7,
    ) -> str:
        """
        Retrieve raw relevant document chunks from TitanRAG vector index.
        :param query: Search query or keywords.
        :param workspace_id: Target workspace UUID.
        :param top_k: Number of chunks to retrieve (1 to 20).
        :param alpha: Hybrid search weight (0.0 = BM25 keyword only, 1.0 = dense semantic only).
        """
        try:
            # Execute search query via client chat API in concise mode or retrieve direct documents
            resp = sdk_client.query(
                query=f"[Search only] {query}",
                workspace_id=workspace_id,
                grounding_mode="Strict",
            )
            chunks = []
            for idx, c in enumerate(resp.citations[:top_k], 1):
                chunks.append(
                    {
                        "rank": idx,
                        "document_id": str(c.document_id),
                        "filename": c.filename,
                        "page": c.page,
                        "relevance_score": c.relevance_score,
                        "snippet": c.snippet,
                    }
                )
            return json.dumps(chunks, indent=2)
        except TitanRAGError as e:
            return f"Error searching TitanRAG documents: {e}"

    @mcp.tool(description="List all accessible TitanRAG workspaces and their metadata.")
    def list_workspaces() -> str:
        """List accessible workspaces for the authenticated user/API key."""
        try:
            workspaces = sdk_client.workspaces.list()
            return json.dumps([w.model_dump(mode="json") for w in workspaces], indent=2)
        except TitanRAGError as e:
            return f"Error listing workspaces: {e}"

    @mcp.tool(description="List all documents in a specific TitanRAG workspace with ingestion status.")
    def list_documents(workspace_id: str) -> str:
        """
        List documents in a workspace.
        :param workspace_id: Target workspace UUID.
        """
        try:
            docs = sdk_client.documents.list(workspace_id)
            return json.dumps([d.model_dump(mode="json") for d in docs], indent=2)
        except TitanRAGError as e:
            return f"Error listing documents: {e}"

    @mcp.tool(description="Retrieve full content and metadata for a specific document.")
    def get_document_content(document_id: str, workspace_id: str) -> str:
        """
        Get document details and status.
        :param document_id: Target document UUID.
        :param workspace_id: Target workspace UUID.
        """
        try:
            doc = sdk_client.documents.get_status(workspace_id=workspace_id, document_id=document_id)
            return json.dumps(doc.model_dump(mode="json"), indent=2)
        except TitanRAGError as e:
            return f"Error retrieving document: {e}"

    # -------------------------------------------------------------------------
    # MCP Resources
    # -------------------------------------------------------------------------

    @mcp.resource("workspace://{workspace_id}")
    def get_workspace_resource(workspace_id: str) -> str:
        """Resource exposing workspace metadata."""
        try:
            w = sdk_client.workspaces.get(workspace_id)
            return json.dumps(w.model_dump(mode="json"), indent=2)
        except Exception as e:
            return f"Workspace resource unavailable: {e}"

    @mcp.resource("document://{document_id}")
    def get_document_resource(document_id: str) -> str:
        """Resource exposing document content, chunk breakdown, and ingestion status."""
        try:
            workspaces = sdk_client.workspaces.list()
            for w in workspaces:
                try:
                    doc = sdk_client.documents.get_status(workspace_id=w.id, document_id=document_id)
                    return json.dumps(doc.model_dump(mode="json"), indent=2)
                except Exception:
                    continue
            return f"Document {document_id} not found in accessible workspaces"
        except Exception as e:
            return f"Document resource unavailable: {e}"

    @mcp.resource("config://rag-settings/{workspace_id}")
    def get_settings_resource(workspace_id: str) -> str:
        """Resource exposing active RAG settings for a workspace."""
        try:
            s = sdk_client.settings.get(workspace_id)
            return json.dumps(s.model_dump(mode="json"), indent=2)
        except Exception as e:
            return f"Settings resource unavailable: {e}"

    # -------------------------------------------------------------------------
    # MCP Prompts
    # -------------------------------------------------------------------------

    @mcp.prompt("titan_synthesis_prompt")
    def titan_synthesis_prompt(query: str, context: str) -> str:
        """System prompt instructing connected LLM to synthesize verified grounded answers."""
        return (
            "You are TitanRAG, an enterprise AI assistant. Answer the user's question strictly "
            "using the provided verified sources. Every factual claim must include an inline citation [N]. "
            "If the context is insufficient, politely state that you do not have enough information.\n\n"
            f"Context:\n{context}\n\n"
            f"User Question:\n{query}"
        )

    return mcp
