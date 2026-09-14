import json

from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.logging import logger

SUGGESTION_PROMPT = """You are a follow-up question generator for an enterprise knowledge retrieval system.
Given the user query and the assistant's answer, generate 2-3 logical follow-up questions that the user might want to explore next.
Return a strict JSON array of strings:
["Follow-up question 1?", "Follow-up question 2?", "Follow-up question 3?"]
Output ONLY the JSON array.
"""


class FollowUpSuggestionsGenerator:
    """Generates context-aware follow-up question suggestions."""

    async def generate_suggestions(self, query: str, answer: str) -> list[str]:
        if not answer or len(answer) < 30:
            return []

        messages = [
            {"role": "system", "content": SUGGESTION_PROMPT},
            {
                "role": "user",
                "content": f"User Query: {query}\n\nAssistant Answer:\n{answer[:800]}\n\nFollow-up Questions (JSON):",
            },
        ]
        try:
            res = await litellm_client.acompletion(messages=messages, temperature=0.3, max_tokens=150)
            content = res["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())
            if isinstance(data, list):
                return [str(q).strip() for q in data[:3] if isinstance(q, str)]
        except Exception as e:
            logger.debug("suggestions_generation_failed", error=str(e))

        return []


suggestions_generator = FollowUpSuggestionsGenerator()
