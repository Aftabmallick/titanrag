import math

from titan_backend.clients.litellm_client import litellm_client
from titan_backend.core.logging import logger

HYDE_PROMPT = """You are a technical document generator for a Hypothetical Document Embeddings (HyDE) pipeline.
Given a user question, write a short, plausible, and factual-sounding technical passage (1-2 paragraphs) that answers the question directly.
Use formal documentation language. Do not explain yourself or use conversational filler.
"""


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class HyDEGenerator:
    """Generates hypothetical answer passages and blended query-hypo dense embeddings."""

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
                hypo = str(choices[0]["message"]["content"]).strip()
                logger.info("hyde_passage_generated", query_length=len(query), hypo_length=len(hypo))
                return str(hypo)
        except Exception as e:
            logger.warning("hyde_generation_failed_falling_back", error=str(e))

        return query

    async def generate_blended_embedding(
        self,
        query: str,
        alpha: float = 0.5,
        model: str | None = None,
    ) -> list[float]:
        """Generates a blended embedding fusing the raw query and hypothetical document.

        Formula: norm(alpha * embed(query) + (1 - alpha) * embed(hypo))
        Prevents semantic drift from hallucinated entities while gaining document-passage alignment.
        """
        hypo = await self.generate_hypothetical_document(query)
        try:
            embeddings = await litellm_client.aembedding([query, hypo], model=model)
            q_vec = embeddings[0]
            h_vec = embeddings[1]

            blended = [alpha * q + (1.0 - alpha) * h for q, h in zip(q_vec, h_vec, strict=True)]
            return _normalize(blended)
        except Exception as e:
            logger.warning("hyde_blended_embedding_failed", error=str(e))
            # Fallback to direct query embedding
            q_vecs = await litellm_client.aembedding([query], model=model)
            return q_vecs[0]


hyde_generator = HyDEGenerator()
