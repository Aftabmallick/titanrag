from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.logging import logger

HYDE_PROMPT = """You are a technical document generator for a Hypothetical Document Embeddings (HyDE) pipeline.
Given a user question, write a short, plausible, and factual-sounding technical passage (1-2 paragraphs) that answers the question directly.
Use formal documentation language. Do not explain yourself or use conversational filler.
"""


class HyDEGenerator:
    """Generates a hypothetical answer passage to be embedded instead of or alongside the raw question."""

    async def generate_hypothetical_document(self, query: str) -> str:
        messages = [
            {"role": "system", "content": HYDE_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nHypothetical Passage:"},
        ]
        try:
            response = await litellm_client.acompletion(
                messages=messages,
                temperature=0.3,
                max_tokens=250,
            )
            choices = response.get("choices", [])
            if choices:
                hypo = choices[0]["message"]["content"].strip()
                logger.info("hyde_passage_generated", query_length=len(query), hypo_length=len(hypo))
                return hypo
        except Exception as e:
            logger.warning("hyde_generation_failed_falling_back", error=str(e))

        return query


hyde_generator = HyDEGenerator()
