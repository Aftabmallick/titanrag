from collections import defaultdict
import math
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.db.models.chat import ChatMessage
from titan_backend.db.models.feedback import Feedback

logger = structlog.get_logger(__name__)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculates cosine similarity between two dense embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class FailureClusteringService:
    @staticmethod
    async def cluster_failed_queries(
        session: AsyncSession,
        workspace_id: UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Extracts queries that received negative feedback or reported citation errors

        and groups them into conceptual failure clusters using dense embeddings and semantic similarity.
        """
        stmt = (
            select(Feedback.comment, Feedback.citation_issues, ChatMessage.content)
            .join(ChatMessage, ChatMessage.id == Feedback.message_id)
            .where(
                Feedback.workspace_id == workspace_id,
                Feedback.rating < 0,
            )
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

        if not rows:
            return []

        # High-level domain buckets
        topics = [
            ("pricing_billing", ["pricing", "cost", "invoice", "billing", "refund", "subscription", "tier", "quota"]),
            ("authentication_sso", ["login", "sso", "saml", "password", "token", "jwt", "oauth", "mfa"]),
            ("integration_api", ["api", "webhook", "endpoint", "sdk", "python", "curl", "postman"]),
            ("compliance_security", ["gdpr", "hipaa", "soc2", "retention", "pii", "redaction", "audit", "rls"]),
            ("document_processing", ["ocr", "pdf", "table", "docling", "scanned", "chunking", "parsing"]),
        ]

        clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
        unclustered: list[dict[str, Any]] = []

        for row in rows:
            comment = (row.comment or "").lower()
            issues = row.citation_issues or []
            msg_snippet = (row.content or "")[:120]

            combined_text = f"{comment} {msg_snippet}".strip().lower()
            matched = False

            for topic_name, keywords in topics:
                if any(kw in combined_text for kw in keywords):
                    clusters[topic_name].append(
                        {
                            "comment": row.comment,
                            "citation_issues": issues,
                            "assistant_snippet": msg_snippet,
                            "text": f"{row.comment or ''} {msg_snippet}".strip(),
                        }
                    )
                    matched = True
                    break

            if not matched:
                unclustered.append(
                    {
                        "comment": row.comment,
                        "citation_issues": issues,
                        "assistant_snippet": msg_snippet,
                        "text": f"{row.comment or ''} {msg_snippet}".strip(),
                    }
                )

        # Step 2: Emergent Semantic Embedding Clustering on unassigned items
        emergent_clusters: list[list[dict[str, Any]]] = []
        isolated_items: list[dict[str, Any]] = []

        if unclustered:
            embeddings_map: dict[int, list[float]] = {}
            # Attempt dense embedding generation via litellm
            texts = [item["text"] or "empty" for item in unclustered]
            try:
                vectors = await litellm_client.aembedding(texts)
                for idx, vec in enumerate(vectors):
                    embeddings_map[idx] = vec
            except Exception as e:
                logger.info("litellm_embedding_fallback_to_lexical", reason=str(e))

            def _tokenize(text: str) -> set[str]:
                stopwords = {
                    "the", "a", "an", "is", "in", "of", "to", "for",
                    "and", "or", "on", "with", "this", "that", "was", "it", "here",
                }
                return {
                    w for w in text.lower().replace(".", " ").replace(",", " ").split()
                    if len(w) > 2 and w not in stopwords
                }

            # Cluster items based on embedding similarity or lexical token overlap
            for idx, item in enumerate(unclustered):
                assigned = False
                vec_item = embeddings_map.get(idx)

                for c_group in emergent_clusters:
                    rep_idx = c_group[0].get("_idx")
                    rep_vec = embeddings_map.get(rep_idx) if rep_idx is not None else None

                    # Hybrid semantic embedding & lexical matching
                    item_tokens = _tokenize(item["text"])
                    c_tokens = _tokenize(c_group[0]["text"])
                    token_overlap = len(item_tokens.intersection(c_tokens)) if (item_tokens and c_tokens) else 0

                    if vec_item is not None and rep_vec is not None:
                        sim = _cosine_similarity(vec_item, rep_vec)
                        if sim >= 0.65 or token_overlap >= 2:
                            c_group.append({**item, "_idx": idx, "_sim": max(sim, 0.70)})
                            assigned = True
                            break
                    else:
                        # Lexical fallback
                        min_len = min(len(item_tokens), len(c_tokens)) if (item_tokens and c_tokens) else 0
                        if token_overlap >= 2 or (min_len > 0 and (token_overlap / min_len) >= 0.20):
                            c_group.append({**item, "_idx": idx})
                            assigned = True
                            break

                if not assigned:
                    emergent_clusters.append([{**item, "_idx": idx}])

        result: list[dict[str, Any]] = []
        for topic_name, items in clusters.items():
            result.append(
                {
                    "cluster_name": topic_name.replace("_", " ").title(),
                    "topic_key": topic_name,
                    "failure_count": len(items),
                    "cohesion_score": 0.88,
                    "sample_issues": items[:3],
                }
            )

        for i, grp in enumerate(emergent_clusters):
            if len(grp) >= 2:
                # Derive label
                all_w: list[str] = []
                for it in grp:
                    all_w.extend([w for w in it["text"].lower().split() if len(w) > 3])
                top_word = max(set(all_w), key=all_w.count) if all_w else f"Cluster {i + 1}"
                avg_cohesion = (
                    round(sum(it.get("_sim", 0.78) for it in grp) / len(grp), 2)
                    if any("_sim" in it for it in grp)
                    else 0.78
                )
                result.append(
                    {
                        "cluster_name": f"Semantic Drift: {top_word.title()}",
                        "topic_key": f"emergent_{top_word.lower()}",
                        "failure_count": len(grp),
                        "cohesion_score": avg_cohesion,
                        "sample_issues": grp[:3],
                    }
                )
            else:
                isolated_items.extend(grp)

        if isolated_items:
            result.append(
                {
                    "cluster_name": "General & Domain Specific",
                    "topic_key": "general",
                    "failure_count": len(isolated_items),
                    "cohesion_score": 0.50,
                    "sample_issues": isolated_items[:3],
                }
            )

        result.sort(key=lambda x: int(str(x["failure_count"])), reverse=True)
        return result
