"""
Knowledge Graph Semantic Extractor.
Extracts semantic entities and relational edges from unstructured text chunks
via dual-layer architecture: deep LLM structured JSON parsing with open-domain
syntactic & NER pattern fallback.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.graph.extractor")

# Broad technology, protocol, and systems vocabulary
EXPANDED_TECH_PATTERNS = (
    r"\b(Python|PostgreSQL|Redis|Qdrant|Docker|Kubernetes|FastAPI|Celery|Neo4j|"
    r"SAML|OAuth2|GraphQL|REST|TypeScript|React|Next\.js|MinIO|Milvus|Pinecone|"
    r"ChromaDB|Weaviate|LangChain|LlamaIndex|PyTorch|TensorFlow|Transformers|"
    r"vLLM|Triton|Ollama|LiteLLM|Kafka|RabbitMQ|ClickHouse|Cassandra|MongoDB|"
    r"Elasticsearch|OpenSearch|Nginx|Envoy|gRPC|WebSocket|WebRTC|OpenTelemetry|"
    r"Prometheus|Grafana|Linux|Ubuntu|Alpine|Terraform|Ansible|Helm|ArgoCD)\b"
)

# Open-domain entity patterns: organizations, products, and capitalized proper nouns
ORG_PATTERNS = (
    r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*\s+"
    r"(?:Inc|Corp|LLC|Ltd|Technologies|Systems|Labs|Foundation|Group|Company|Platform|Solutions|AI|HQ))\b"
)

PROPER_NOUN_PATTERNS = r"\b([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)+)\b"
ACRONYM_PATTERNS = r"\b([A-Z]{2,6})\b"

# Generalized relational grammar patterns (Transitive verbs & prepositions)
RELATION_GRAMMAR = [
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+(?:has\s+)?acquired\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "ACQUIRED",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+integrates\s+(?:directly\s+)?with\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "INTEGRATES_WITH",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+uses\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "USES",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+manages\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "MANAGES",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+authenticates\s+via\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "AUTHENTICATES_VIA",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+depends\s+on\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "DEPENDS_ON",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+implements\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "IMPLEMENTS",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+is\s+(?:developed|created|built)\s+by\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "DEVELOPED_BY",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+is\s+deployed\s+to\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "DEPLOYED_TO",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+stores\s+(?:data\s+in|state\s+in)\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "STORES_IN",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+connects\s+to\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "CONNECTS_TO",
    ),
    (
        r"(?P<src>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)\s+operates\s+(?P<tgt>[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*)",
        "OPERATES",
    ),
]


class KnowledgeGraphExtractor:
    """
    Extracts semantic entities and relational edges from document chunks.
    Combines fast open-domain syntactic parsing with deep LLM structured JSON extraction.
    """

    @classmethod
    def extract_from_chunk(cls, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Fast in-process open-domain extraction.
        Extracts entities across tech vocabularies, organizations, proper nouns, and relational edges.
        """
        entities_map: dict[str, dict[str, Any]] = {}
        relationships: list[dict[str, Any]] = []

        if not text:
            return [], []

        # 1. Extract Technologies & Protocols
        for match in re.finditer(EXPANDED_TECH_PATTERNS, text, re.IGNORECASE):
            name = match.group(0)
            entities_map[name.upper()] = {
                "name": name,
                "type": "TECHNOLOGY",
                "properties": {"mention_type": "technology_pattern"},
            }

        # 2. Extract Named Organizations
        for match in re.finditer(ORG_PATTERNS, text):
            name = match.group(0).strip()
            entities_map[name.upper()] = {
                "name": name,
                "type": "ORGANIZATION",
                "properties": {"mention_type": "organization_pattern"},
            }

        # 3. Extract Open Proper Nouns (if not already found)
        for match in re.finditer(PROPER_NOUN_PATTERNS, text):
            name = match.group(0).strip()
            # Ignore common sentence starters
            if name.split()[0].lower() in {
                "in",
                "on",
                "at",
                "the",
                "this",
                "that",
                "these",
                "after",
                "before",
                "during",
            }:
                continue
            if name.upper() not in entities_map:
                entities_map[name.upper()] = {
                    "name": name,
                    "type": "ENTITY",
                    "properties": {"mention_type": "named_entity"},
                }

        # 4. Extract Relational Statements
        for pattern, rel_type in RELATION_GRAMMAR:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                src = match.group("src").strip()
                tgt = match.group("tgt").strip()

                if src.upper() not in entities_map:
                    entities_map[src.upper()] = {
                        "name": src,
                        "type": "CONCEPT",
                        "properties": {},
                    }
                if tgt.upper() not in entities_map:
                    entities_map[tgt.upper()] = {
                        "name": tgt,
                        "type": "CONCEPT",
                        "properties": {},
                    }

                relationships.append(
                    {
                        "source": src,
                        "target": tgt,
                        "relation": rel_type,
                        "quote": match.group(0).strip(),
                        "weight": 1.0,
                    }
                )

        return list(entities_map.values()), relationships

    @classmethod
    async def aextract_from_chunk(
        cls,
        text: str,
        use_llm: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Deep extraction using LiteLLM structured JSON generation with graceful fallback
        to the in-process heuristic extractor.
        """
        if not text or not text.strip():
            return [], []

        if not use_llm:
            return cls.extract_from_chunk(text)

        try:
            from titan_backend.clients.litellm_client import litellm_client

            prompt = (
                "You are an expert knowledge graph extraction engine. "
                "Extract all salient entities (technologies, organizations, people, locations, concepts) "
                "and their explicit relationships from the text.\n\n"
                "Respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                '  "entities": [{"name": "string", "type": "ORGANIZATION|TECHNOLOGY|PERSON|CONCEPT|LOCATION", "properties": {}}],\n'
                '  "relationships": [{"source": "string", "target": "string", "relation": "UPPERCASE_REL_TYPE", "quote": "string", "weight": 1.0}]\n'
                "}\n\n"
                f"TEXT:\n{text[:4000]}"
            )

            messages = [
                {"role": "system", "content": "You are a JSON-only knowledge graph extraction model."},
                {"role": "user", "content": prompt},
            ]

            response = await litellm_client.acompletion(
                messages=messages,
                temperature=0.0,
                max_tokens=800,
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            # Clean markdown JSON fences if returned
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            parsed = json.loads(content.strip())
            entities = parsed.get("entities", [])
            relationships = parsed.get("relationships", [])

            if isinstance(entities, list) and isinstance(relationships, list) and (entities or relationships):
                return entities, relationships

        except Exception as e:
            logger.warning("llm_graph_extraction_fallback", error=str(e))

        # Fallback to local heuristic extractor
        return cls.extract_from_chunk(text)
