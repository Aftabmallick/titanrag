from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from titan_backend.core.dependencies import CurrentUser, get_current_user
from titan_backend.graph.extractor import KnowledgeGraphExtractor
from titan_backend.graph.retriever import GraphHybridRetriever
from titan_backend.graph.store import get_graph_store

router = APIRouter(prefix="/workspaces/{workspace_id}/graph", tags=["knowledge-graph"])


class GraphExtractRequest(BaseModel):
    text: str = Field(..., min_length=5)


class GraphQueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    max_hops: int = Field(default=2, ge=1, le=4)
    limit: int = Field(default=20, ge=1, le=100)


@router.get("")
async def get_workspace_graph_elements(
    workspace_id: uuid.UUID,
    limit: int = Query(default=150, ge=10, le=500),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return Cytoscape.js compatible graph elements (nodes & edges) for interactive visualization."""
    store = get_graph_store()
    elements = await store.get_workspace_graph(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        limit=limit,
    )
    return elements


@router.post("/query")
async def query_knowledge_graph(
    workspace_id: uuid.UUID,
    payload: GraphQueryRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Execute graph-augmented entity expansion Cypher queries for a user prompt."""
    formatted_context, facts = await GraphHybridRetriever.retrieve_graph_context(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace_id,
        query=payload.query,
        max_hops=payload.max_hops,
        limit=payload.limit,
    )
    return {
        "query": payload.query,
        "facts_count": len(facts),
        "facts": facts,
        "formatted_context": formatted_context,
    }


@router.post("/extract")
async def extract_graph_from_text(
    workspace_id: uuid.UUID,
    payload: GraphExtractRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Test extractor on sample chunk text."""
    entities, relations = KnowledgeGraphExtractor.extract_from_chunk(payload.text)
    return {
        "entities_count": len(entities),
        "entities": entities,
        "relations_count": len(relations),
        "relations": relations,
    }
