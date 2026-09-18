import uuid
from typing import Any

import structlog
from titan_backend.graph.extractor import KnowledgeGraphExtractor
from titan_backend.graph.store import get_graph_store

logger = structlog.get_logger("titanrag.graph.retriever")


class GraphHybridRetriever:
    """
    Graph-augmented retrieval engine.
    Extracts query entities, queries the Neo4j sub-graph neighborhood,
    and constructs relational fact blocks that enrich vector context.
    """

    @classmethod
    async def retrieve_graph_context(
        cls,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        query: str,
        max_hops: int = 2,
        limit: int = 20,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Extracts entities from query, traverses knowledge graph, and formats factual context string.
        """
        entities, _ = KnowledgeGraphExtractor.extract_from_chunk(query)
        if not entities:
            # Fallback: extract capitalized tokens
            words = [w.strip("?,.!\"'") for w in query.split() if len(w) > 3 and w[0].isupper()]
            entities = [{"name": w, "type": "KEYWORD"} for w in words]

        if not entities:
            return "", []

        entity_names = [e["name"] for e in entities]
        store = get_graph_store()
        facts = await store.query_neighborhood(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            entity_names=entity_names,
            max_hops=max_hops,
            limit=limit,
        )

        if not facts:
            return "", []

        fact_lines = ["### Knowledge Graph Relational Facts:"]
        for f in facts:
            source = f["source"]
            target = f["target"]
            for rel in f["relations"]:
                rel_type = rel.get("type", "RELATED_TO")
                quote = f' (Ref: "{rel["quote"]}")' if rel.get("quote") else ""
                fact_lines.append(f"- ({source}) --[{rel_type}]--> ({target}){quote}")

        formatted_context = "\n".join(fact_lines) + "\n\n"
        return formatted_context, facts
