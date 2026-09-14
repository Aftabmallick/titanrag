import json

from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.logging import logger

MULTI_HOP_DECOMPOSITION_PROMPT = """You are an agentic query decomposition assistant for an enterprise RAG system.
Given a complex, multi-part, or comparative user query, decompose it into 2-4 distinct, simpler sub-queries that can each be searched independently in the knowledge base.
Return a strict JSON array of strings:
["Sub-query 1", "Sub-query 2"]
If the query cannot be meaningfully decomposed, return an array containing only the original query.
Output ONLY the JSON array.
"""


class MultiHopQueryDecomposer:
    """Deconstructs multi-part or comparative queries into independent sub-queries for parallel

    retrieval.
    """

    async def decompose_query(self, query: str) -> list[str]:
        messages = [
            {"role": "system", "content": MULTI_HOP_DECOMPOSITION_PROMPT},
            {"role": "user", "content": f"Query: {query}\n\nDecomposed Sub-queries (JSON):"},
        ]
        try:
            res = await litellm_client.acompletion(messages=messages, temperature=0.0, max_tokens=200)
            content = res["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            sub_queries = json.loads(content.strip())
            if isinstance(sub_queries, list) and len(sub_queries) > 0:
                valid_subs = [str(q).strip() for q in sub_queries if isinstance(q, str) and q.strip()]
                if valid_subs:
                    logger.info("query_decomposed", original=query, sub_queries=valid_subs)
                    return valid_subs
        except Exception as e:
            logger.warning("query_decomposition_failed", error=str(e))

        return [query]


multi_hop_decomposer = MultiHopQueryDecomposer()
