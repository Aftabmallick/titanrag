from typing import Any


def build_teams_adaptive_card(
    query: str,
    answer: str,
    citations: list[dict[str, Any]],
    workspace_name: str = "TitanRAG",
) -> dict[str, Any]:
    """Format RAG answer and citations into Microsoft Teams Adaptive Card v1.4 schema."""
    body_elements: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "size": "Medium",
            "weight": "Bolder",
            "text": f"TitanRAG Search: {query}",
        },
        {
            "type": "TextBlock",
            "text": answer,
            "wrap": True,
        },
    ]

    if citations:
        citation_facts = []
        for i, cit in enumerate(citations[:5], start=1):
            doc_title = cit.get("title", f"Document #{i}")
            page_num = cit.get("page_number")
            val = f"Page {page_num}" if page_num else "Referenced"
            citation_facts.append({"title": f"Source {i} ({doc_title})", "value": val})

        body_elements.append(
            {
                "type": "FactSet",
                "facts": citation_facts,
            }
        )

    body_elements.append(
        {
            "type": "TextBlock",
            "size": "Small",
            "isSubtle": True,
            "text": f"Workspace: {workspace_name} | TitanRAG Enterprise",
        }
    )

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body_elements,
                },
            }
        ],
    }
