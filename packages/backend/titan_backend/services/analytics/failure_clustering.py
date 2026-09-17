from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from titan_backend.db.models.chat import ChatMessage
from titan_backend.db.models.feedback import Feedback

logger = structlog.get_logger(__name__)


class FailureClusteringService:
    @staticmethod
    async def cluster_failed_queries(
        session: AsyncSession,
        workspace_id: UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Extracts queries that received negative feedback or reported citation errors

        and groups them into conceptual failure clusters based on shared keywords.
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

        # Keyword-based clustering bucketizer
        clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)

        topics = [
            ("pricing_billing", ["pricing", "cost", "invoice", "billing", "refund", "subscription", "tier", "quota"]),
            ("authentication_sso", ["login", "sso", "saml", "password", "token", "jwt", "oauth", "mfa"]),
            ("integration_api", ["api", "webhook", "endpoint", "sdk", "python", "curl", "postman"]),
            ("compliance_security", ["gdpr", "hipaa", "soc2", "retention", "pii", "redaction", "audit", "rls"]),
            ("document_processing", ["ocr", "pdf", "table", "docling", "scanned", "chunking", "parsing"]),
        ]

        unclustered = []

        for row in rows:
            comment = (row.comment or "").lower()
            issues = row.citation_issues or []
            msg_snippet = (row.content or "")[:120]

            combined_text = f"{comment} {msg_snippet}".lower()
            matched = False

            for topic_name, keywords in topics:
                if any(kw in combined_text for kw in keywords):
                    clusters[topic_name].append({
                        "comment": row.comment,
                        "citation_issues": issues,
                        "assistant_snippet": msg_snippet,
                    })
                    matched = True
                    break

            if not matched:
                unclustered.append({
                    "comment": row.comment,
                    "citation_issues": issues,
                    "assistant_snippet": msg_snippet,
                })

        # Step 2: Emergent Semantic Similarity Clustering on unassigned items
        emergent_clusters: list[list[dict[str, Any]]] = []
        isolated_items: list[dict[str, Any]] = []

        def _tokenize(text: str) -> set[str]:
            stopwords = {"the", "a", "an", "is", "in", "of", "to", "for", "and", "or", "on", "with", "this", "that", "was", "it", "here"}
            words = {w for w in text.lower().replace(".", " ").replace(",", " ").split() if len(w) > 2 and w not in stopwords}
            return words

        for item in unclustered:
            item_tokens = _tokenize(f"{item['comment'] or ''} {item['assistant_snippet'] or ''}")
            assigned = False
            for c_group in emergent_clusters:
                # Compare against centroid/first item of cluster
                c_tokens = _tokenize(f"{c_group[0]['comment'] or ''} {c_group[0]['assistant_snippet'] or ''}")
                if c_tokens and item_tokens:
                    overlap = len(item_tokens.intersection(c_tokens))
                    min_len = min(len(item_tokens), len(c_tokens))
                    if overlap >= 2 or (min_len > 0 and (overlap / min_len) >= 0.20):
                        c_group.append(item)
                        assigned = True
                        break
            if not assigned:
                emergent_clusters.append([item])

        result = []
        for topic_name, items in clusters.items():
            result.append({
                "cluster_name": topic_name.replace("_", " ").title(),
                "topic_key": topic_name,
                "failure_count": len(items),
                "cohesion_score": 0.88,
                "sample_issues": items[:3],
            })

        for i, grp in enumerate(emergent_clusters):
            if len(grp) >= 2:
                # Derive title from most frequent token
                all_w = []
                for it in grp:
                    all_w.extend(_tokenize(f"{it['comment'] or ''} {it['assistant_snippet'] or ''}"))
                top_word = max(set(all_w), key=all_w.count) if all_w else f"Cluster {i+1}"
                result.append({
                    "cluster_name": f"Semantic Drift: {top_word.title()}",
                    "topic_key": f"emergent_{top_word.lower()}",
                    "failure_count": len(grp),
                    "cohesion_score": 0.76,
                    "sample_issues": grp[:3],
                })
            else:
                isolated_items.extend(grp)

        if isolated_items:
            result.append({
                "cluster_name": "General & Domain Specific",
                "topic_key": "general",
                "failure_count": len(isolated_items),
                "cohesion_score": 0.50,
                "sample_issues": isolated_items[:3],
            })

        result.sort(key=lambda x: x["failure_count"], reverse=True)
        return result
