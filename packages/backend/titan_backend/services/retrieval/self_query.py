import json
from typing import Any, NamedTuple

from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.logging import logger


class SelfQueryFilter(NamedTuple):
    cleaned_query: str
    doc_type: str | None = None
    folder: str | None = None
    tags: list[str] | None = None
    created_after_year: int | None = None


SELF_QUERY_SYSTEM_PROMPT = """You are a metadata extraction parser for a document retrieval system.
Given a user query, determine if the user is explicitly constraining the search by metadata:
- document type (doc_type: e.g. "nda", "contract", "invoice", "specification", "policy", "report", "csv", "code")
- folder (e.g. "legal", "engineering", "finance")
- tags (list of string tags)
- created_after_year (e.g. 2023, 2024)

Return a strict JSON object with fields:
{
  "cleaned_query": "the semantic topic query without metadata constraints",
  "doc_type": "string or null",
  "folder": "string or null",
  "tags": ["list of strings or null"],
  "created_after_year": "integer or null"
}
Output ONLY valid JSON.
"""


class SelfQueryEngine:
    """Extracts structured metadata pre-filters from natural language queries."""

    async def extract_filters(self, query: str) -> SelfQueryFilter:
        # Fast heuristic check: if query has no year or doc-type keywords, return query as-is
        lower = query.lower()
        has_keywords = any(
            kw in lower
            for kw in ["from 20", "in 20", "nda", "contract", "invoice", "folder", "policy", "report", "spec"]
        )
        if not has_keywords:
            return SelfQueryFilter(cleaned_query=query)

        messages = [
            {"role": "system", "content": SELF_QUERY_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        try:
            res = await litellm_client.acompletion(messages=messages, temperature=0.0, max_tokens=200)
            content = res["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            data: dict[str, Any] = json.loads(content.strip())
            return SelfQueryFilter(
                cleaned_query=data.get("cleaned_query") or query,
                doc_type=data.get("doc_type"),
                folder=data.get("folder"),
                tags=data.get("tags"),
                created_after_year=data.get("created_after_year"),
            )
        except Exception as e:
            logger.debug("self_query_extraction_skipped", error=str(e))
            return SelfQueryFilter(cleaned_query=query)


self_query_engine = SelfQueryEngine()
