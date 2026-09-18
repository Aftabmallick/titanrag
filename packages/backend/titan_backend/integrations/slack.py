import hashlib
import hmac
import time
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.integrations.slack")


def verify_slack_signature(
    signing_secret: str,
    body_bytes: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify incoming Slack webhook request authenticity using HMAC-SHA256."""
    try:
        req_time = int(timestamp)
        # Replay attack prevention (5 minute window)
        if abs(time.time() - req_time) > 60 * 5:
            return False

        sig_basestring = f"v0:{timestamp}:{body_bytes.decode('utf-8')}".encode()
        computed_sig = (
            "v0="
            + hmac.new(
                signing_secret.encode("utf-8"),
                sig_basestring,
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(computed_sig, signature)
    except Exception as e:
        logger.warning("slack_signature_verification_error", error=str(e))
        return False


def build_slack_rag_response(
    query: str,
    answer: str,
    citations: list[dict[str, Any]],
    workspace_name: str = "TitanRAG",
) -> dict[str, Any]:
    """Format RAG answer and citations into rich Slack Block Kit layout."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"TitanRAG Search: {query[:50]}...",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": answer,
            },
        },
        {"type": "divider"},
    ]

    if citations:
        citation_lines = []
        for i, cit in enumerate(citations[:5], start=1):
            doc_title = cit.get("title", f"Document #{i}")
            page_num = cit.get("page_number")
            page_str = f" (Page {page_num})" if page_num else ""
            citation_lines.append(f"• *[Source {i}]* {doc_title}{page_str}")

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Verified Sources:*\n" + "\n".join(citation_lines),
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Knowledge Base: *{workspace_name}* | Powered by TitanRAG Enterprise",
                }
            ],
        }
    )

    return {
        "response_type": "in_channel",
        "blocks": blocks,
        "text": answer,
    }
