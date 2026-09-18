import re
from typing import Any
import structlog

logger = structlog.get_logger("titanrag.graph.extractor")

# Common entity regex patterns for fast-path extraction without model latency
TECH_PATTERNS = r"\b(Python|PostgreSQL|Redis|Qdrant|Docker|Kubernetes|FastAPI|Celery|Neo4j|SAML|OAuth2|GraphQL|REST)\b"
ORG_PATTERNS = r"\b([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)*\s+(?:Inc|Corp|LLC|Ltd|Technologies|Systems|Labs|Foundation|Group))\b"
RELATION_PATTERNS = [
    (r"(?P<src>[A-Z][A-Za-z0-9_]+)\s+acquired\s+(?P<tgt>[A-Z][A-Za-z0-9_]+)", "ACQUIRED"),
    (r"(?P<src>[A-Z][A-Za-z0-9_]+)\s+integrates\s+with\s+(?P<tgt>[A-Z][A-Za-z0-9_]+)", "INTEGRATES_WITH"),
    (r"(?P<src>[A-Z][A-Za-z0-9_]+)\s+uses\s+(?P<tgt>[A-Z][A-Za-z0-9_]+)", "USES"),
    (r"(?P<src>[A-Z][A-Za-z0-9_]+)\s+manages\s+(?P<tgt>[A-Z][A-Za-z0-9_]+)", "MANAGES"),
    (r"(?P<src>[A-Z][A-Za-z0-9_]+)\s+authenticates\s+via\s+(?P<tgt>[A-Z][A-Za-z0-9_]+)", "AUTHENTICATES_VIA"),
]


class KnowledgeGraphExtractor:
    """
    Extracts semantic entities and relational edges from document chunks.
    Combines fast in-process extraction patterns with LLM structured parsing.
    """

    @classmethod
    def extract_from_chunk(cls, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entities_map: dict[str, dict[str, Any]] = {}
        relationships: list[dict[str, Any]] = []

        # 1. Extract Technologies
        for match in re.finditer(TECH_PATTERNS, text, re.IGNORECASE):
            name = match.group(0)
            entities_map[name.upper()] = {
                "name": name,
                "type": "TECHNOLOGY",
                "properties": {},
            }

        # 2. Extract Organizations / Entities
        for match in re.finditer(ORG_PATTERNS, text):
            name = match.group(0)
            entities_map[name.upper()] = {
                "name": name,
                "type": "ORGANIZATION",
                "properties": {},
            }

        # 3. Extract Relational Statements
        for pattern, rel_type in RELATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                src = match.group("src")
                tgt = match.group("tgt")
                if src.upper() not in entities_map:
                    entities_map[src.upper()] = {"name": src, "type": "CONCEPT", "properties": {}}
                if tgt.upper() not in entities_map:
                    entities_map[tgt.upper()] = {"name": tgt, "type": "CONCEPT", "properties": {}}

                relationships.append({
                    "source": src,
                    "target": tgt,
                    "relation": rel_type,
                    "quote": match.group(0),
                    "weight": 1.0,
                })

        return list(entities_map.values()), relationships
