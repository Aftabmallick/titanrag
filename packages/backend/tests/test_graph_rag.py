from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from titan_backend.graph.extractor import KnowledgeGraphExtractor
from titan_backend.graph.retriever import GraphHybridRetriever
from titan_backend.graph.store import Neo4jGraphStore


def test_entity_and_relation_extractor():
    sample_text = (
        "In 2024, TitanCorp acquired DataSystems LLC. "
        "The application integrates with PostgreSQL and uses Docker and Kubernetes for orchestration."
    )

    entities, relationships = KnowledgeGraphExtractor.extract_from_chunk(sample_text)

    entity_names = [e["name"].upper() for e in entities]
    assert "POSTGRESQL" in entity_names
    assert "DOCKER" in entity_names
    assert "KUBERNETES" in entity_names

    rel_types = [r["relation"] for r in relationships]
    assert "ACQUIRED" in rel_types
    assert "INTEGRATES_WITH" in rel_types


@pytest.mark.asyncio
async def test_neo4j_graph_store_offline_graceful():
    store = Neo4jGraphStore(uri="bolt://localhost:9999")
    # Should not crash if Neo4j is offline or unavailable during dev/testing
    is_alive = await store.test_connection()
    assert is_alive is False

    elements = await store.get_workspace_graph(uuid.uuid4(), uuid.uuid4())
    assert elements == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_graph_hybrid_retriever():
    mock_facts = [
        {
            "source": "TitanCorp",
            "source_type": "ORGANIZATION",
            "relations": [{"type": "ACQUIRED", "quote": "TitanCorp acquired DataSystems"}],
            "target": "DataSystems",
            "target_type": "ORGANIZATION",
        }
    ]

    with patch("titan_backend.graph.store.Neo4jGraphStore.query_neighborhood", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_facts

        context, facts = await GraphHybridRetriever.retrieve_graph_context(
            tenant_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            query="What companies did TitanCorp acquire?",
        )

        assert len(facts) == 1
        assert "Knowledge Graph Relational Facts:" in context
        assert "(TitanCorp) --[ACQUIRED]--> (DataSystems)" in context
