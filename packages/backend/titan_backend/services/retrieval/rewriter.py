from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.logging import logger

REWRITE_SYSTEM_PROMPT = """You are a query reformulation assistant for a technical RAG knowledge retrieval system.
Given a conversation history and a user's follow-up query, rewrite the follow-up query into a single, unambiguous, fully self-contained search query.
Resolve all pronouns (e.g. "it", "they", "its", "former", "latter") and implicit references to entities mentioned in the chat history.
DO NOT answer the question. Only output the rewritten search query.
If the query is already self-contained, output it unchanged.
"""


class QueryRewriter:
    """Reformulates multi-turn conversational queries into self-contained search questions."""

    async def rewrite_query(self, current_query: str, chat_history: list[dict[str, str]]) -> str:
        if not chat_history:
            return current_query

        # Filter last 4 messages for concise context
        recent_history = chat_history[-4:]
        history_text = "\n".join(f"{msg['role'].upper()}: {msg['content']}" for msg in recent_history)

        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Conversation History:\n{history_text}\n\nCurrent Follow-up Query: {current_query}\n\nRewritten Query:",
            },
        ]

        try:
            response = await litellm_client.acompletion(
                messages=messages,
                temperature=0.0,
                max_tokens=150,
            )
            choices = response.get("choices", [])
            if choices:
                rewritten = choices[0]["message"]["content"].strip().strip('"')
                if rewritten:
                    logger.info("query_rewritten", original=current_query, rewritten=rewritten)
                    return rewritten
        except Exception as e:
            logger.warning("query_rewrite_failed_falling_back", error=str(e), original=current_query)

        return current_query


query_rewriter = QueryRewriter()
