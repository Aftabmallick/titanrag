import os
from typing import Any
import uuid
import structlog

logger = structlog.get_logger("titanrag.graph.store")


class Neo4jGraphStore:
    """
    Asynchronous Neo4j Graph Database store.
    Provides multi-tenant transactional Cypher operations, APOC optimizations,
    and sub-graph neighborhood traversal for Graph RAG.
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "titan_dev_password")
        self._driver = None

    async def get_driver(self):
        if self._driver is None:
            try:
                from neo4j import AsyncGraphDatabase
                self._driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    max_connection_lifetime=30 * 60,
                    max_connection_pool_size=50,
                )
            except Exception as e:
                logger.warning("neo4j_driver_init_failed", error=str(e))
                return None
        return self._driver

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def test_connection(self) -> bool:
        driver = await self.get_driver()
        if not driver:
            return False
        try:
            async with driver.session() as session:
                result = await session.run("RETURN 1 AS alive")
                record = await result.single()
                return record is not None and record["alive"] == 1
        except Exception as e:
            logger.warning("neo4j_health_check_failed", error=str(e))
            return False

    async def upsert_entities_and_relations(
        self,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        entities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> None:
        """Upsert entities and relational edges isolated by tenant and workspace."""
        driver = await self.get_driver()
        if not driver:
            logger.warning("neo4j_unavailable_skipping_upsert")
            return

        tid = str(tenant_id)
        wid = str(workspace_id)
        did = str(document_id)

        cypher_entity = """
        UNWIND $entities AS ent
        MERGE (e:Entity {tenant_id: $tid, workspace_id: $wid, name: toUpper(ent.name)})
        ON CREATE SET 
            e.display_name = ent.name,
            e.type = ent.type,
            e.document_ids = [$did],
            e.created_at = timestamp()
        ON MATCH SET 
            e.document_ids = CASE 
                WHEN NOT $did IN coalesce(e.document_ids, []) 
                THEN coalesce(e.document_ids, []) + $did 
                ELSE e.document_ids 
            END
        """

        cypher_rel = """
        UNWIND $relationships AS rel
        MATCH (s:Entity {tenant_id: $tid, workspace_id: $wid, name: toUpper(rel.source)})
        MATCH (t:Entity {tenant_id: $tid, workspace_id: $wid, name: toUpper(rel.target)})
        MERGE (s)-[r:RELATION {tenant_id: $tid, workspace_id: $wid, relation_type: toUpper(rel.relation)}]->(t)
        ON CREATE SET
            r.display_relation = rel.relation,
            r.weight = coalesce(rel.weight, 1.0),
            r.quote = rel.quote,
            r.document_ids = [$did]
        ON MATCH SET
            r.weight = coalesce(r.weight, 1.0) + 0.1,
            r.document_ids = CASE 
                WHEN NOT $did IN coalesce(r.document_ids, []) 
                THEN coalesce(r.document_ids, []) + $did 
                ELSE r.document_ids 
            END
        """

        async with driver.session() as session:
            if entities:
                await session.run(
                    cypher_entity,
                    tid=tid,
                    wid=wid,
                    did=did,
                    entities=entities,
                )
            if relationships:
                await session.run(
                    cypher_rel,
                    tid=tid,
                    wid=wid,
                    did=did,
                    relationships=relationships,
                )

    async def query_neighborhood(
        self,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        entity_names: list[str],
        max_hops: int = 2,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Traverse k-hop entity relationships to build contextual sub-graph facts."""
        driver = await self.get_driver()
        if not driver:
            return []

        upper_names = [name.upper().strip() for name in entity_names if name.strip()]
        if not upper_names:
            return []

        cypher = f"""
        MATCH (s:Entity {{tenant_id: $tid, workspace_id: $wid}})
        WHERE s.name IN $names
        MATCH path = (s)-[r:RELATION*1..{max_hops}]-(t:Entity {{tenant_id: $tid, workspace_id: $wid}})
        WITH s, relationships(path) AS rels, t
        LIMIT $limit
        RETURN s.display_name AS source,
               s.type AS source_type,
               [rel IN rels | {{type: rel.display_relation, quote: rel.quote}}] AS relations,
               t.display_name AS target,
               t.type AS target_type
        """

        facts = []
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    tid=str(tenant_id),
                    wid=str(workspace_id),
                    names=upper_names,
                    limit=limit,
                )
                async for record in result:
                    facts.append({
                        "source": record["source"],
                        "source_type": record["source_type"],
                        "relations": record["relations"],
                        "target": record["target"],
                        "target_type": record["target_type"],
                    })
        except Exception as e:
            logger.warning("neo4j_neighborhood_query_error", error=str(e))
        return facts

    async def get_workspace_graph(
        self,
        tenant_id: uuid.UUID,
        workspace_id: uuid.UUID,
        limit: int = 150,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch elements formatted for Cytoscape.js / D3 knowledge graph visualizer."""
        driver = await self.get_driver()
        if not driver:
            return {"nodes": [], "edges": []}

        cypher = """
        MATCH (s:Entity {tenant_id: $tid, workspace_id: $wid})-[r:RELATION {tenant_id: $tid, workspace_id: $wid}]->(t:Entity)
        RETURN s.name AS s_id, s.display_name AS s_label, s.type AS s_type,
               t.name AS t_id, t.display_name AS t_label, t.type AS t_type,
               r.display_relation AS rel_label, r.weight AS weight
        LIMIT $limit
        """
        nodes = {}
        edges = []

        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    tid=str(tenant_id),
                    wid=str(workspace_id),
                    limit=limit,
                )
                async for record in result:
                    s_id = record["s_id"]
                    t_id = record["t_id"]

                    if s_id not in nodes:
                        nodes[s_id] = {
                            "data": {
                                "id": s_id,
                                "label": record["s_label"],
                                "type": record["s_type"],
                            }
                        }
                    if t_id not in nodes:
                        nodes[t_id] = {
                            "data": {
                                "id": t_id,
                                "label": record["t_label"],
                                "type": record["t_type"],
                            }
                        }

                    edges.append({
                        "data": {
                            "id": f"{s_id}_{t_id}_{record['rel_label']}",
                            "source": s_id,
                            "target": t_id,
                            "label": record["rel_label"],
                            "weight": record["weight"],
                        }
                    })
        except Exception as e:
            logger.warning("neo4j_workspace_graph_error", error=str(e))

        return {"nodes": list(nodes.values()), "edges": edges}


_graph_store: Neo4jGraphStore | None = None


def get_graph_store() -> Neo4jGraphStore:
    global _graph_store
    if _graph_store is None:
        _graph_store = Neo4jGraphStore()
    return _graph_store
