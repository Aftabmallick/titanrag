import json
import re
from typing import Any

import structlog
from titan_backend.clients.litellm_client import litellm_client
from titan_backend.services.retrieval.context_packer import PackedSource

logger = structlog.get_logger(__name__)

COMPARISON_SYSTEM_PROMPT = """You are TitanRAG operating in Enterprise Source Comparison Mode.
Your task is to exhaustively compare, contrast, and audit differences between two sets of sources from Document A and Document B.

Your response MUST adhere to this structure:
1. Executive Summary: 2-3 sentences summarizing whether the documents agree or diverge.
2. Side-by-Side Comparison Table: A Markdown table with columns:
   | Dimension / Clause | Document A ({doc_a_name}) | Document B ({doc_b_name}) | Alignment Status |
   Alignment Status must be one of: [AGREEMENT], [DIVERGENCE], [CONTRADICTION], [UNIQUE_TO_A], [UNIQUE_TO_B].
3. Contradiction & Conflict Audit: Detailed analysis of any contradictory figures, dates, liabilities, or terms.
4. Detailed Narrative: Full comparative synthesis citing every single assertion with [Source N].
"""

STRUCTURED_EXTRACT_PROMPT = """Extract and compare the specific assertions made about '{topic}' in the two documents.
Return a valid JSON object strictly matching this schema:
{{
  "summary": "High-level summary of agreement or divergence",
  "dimensions": [
    {{
      "dimension": "e.g., Termination Notice Period",
      "doc_a_claim": "Claim in Doc A with [Source N]",
      "doc_b_claim": "Claim in Doc B with [Source N]",
      "status": "AGREEMENT" | "DIVERGENCE" | "CONTRADICTION" | "UNIQUE_TO_A" | "UNIQUE_TO_B",
      "conflict_severity": "NONE" | "LOW" | "HIGH"
    }}
  ],
  "key_takeaways": ["Key difference 1", "Key difference 2"]
}}
"""


class SourceComparator:
    """Orchestrates structured multi-document comparison, conflict detection, and tabular synthesis."""

    def format_comparison_prompt(
        self,
        sources_doc_a: list[PackedSource],
        sources_doc_b: list[PackedSource],
        topic: str,
    ) -> str:
        doc_a_name = sources_doc_a[0].document_name if sources_doc_a else "Document A"
        doc_b_name = sources_doc_b[0].document_name if sources_doc_b else "Document B"

        all_sources = sources_doc_a + sources_doc_b
        src_blocks = []
        for s in all_sources:
            src_blocks.append(
                f"[Source {s.source_index}] (Doc: {s.document_name}, Page: {s.page_number}):\n{s.text}\n"
            )

        joined_sources = "\n".join(src_blocks)
        sys_prompt = COMPARISON_SYSTEM_PROMPT.format(doc_a_name=doc_a_name, doc_b_name=doc_b_name)

        return (
            f"{sys_prompt}\n\n"
            f"=== TOPIC TO COMPARE ===\n{topic}\n\n"
            f"=== EXTRACTED SOURCES ===\n{joined_sources}\n"
        )

    def detect_simple_conflicts(
        self,
        sources_doc_a: list[PackedSource],
        sources_doc_b: list[PackedSource],
    ) -> list[dict[str, Any]]:
        """Heuristic conflict detection for numbers, percentages, and currencies across doc sources."""
        conflicts = []
        num_pattern = re.compile(r"(\$?\d+(?:,\d{3})*(?:\.\d+)?%?)")

        nums_a = set()
        for s in sources_doc_a:
            for match in num_pattern.findall(s.text):
                nums_a.add(match)

        nums_b = set()
        for s in sources_doc_b:
            for match in num_pattern.findall(s.text):
                nums_b.add(match)

        discrepancies = (nums_a ^ nums_b) - {"0", "1", "2", "3"}
        if discrepancies:
            conflicts.append(
                {
                    "type": "numerical_discrepancy",
                    "details": f"Discrepant figures found across documents: {sorted(list(discrepancies))[:6]}",
                    "severity": "MEDIUM",
                }
            )
        return conflicts

    async def generate_structured_comparison(
        self,
        sources_doc_a: list[PackedSource],
        sources_doc_b: list[PackedSource],
        topic: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Executes LLM comparison returning structured JSON dimensions, status, and severity."""
        prompt = self.format_comparison_prompt(sources_doc_a, sources_doc_b, topic)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"{STRUCTURED_EXTRACT_PROMPT.format(topic=topic)}"},
        ]

        try:
            resp = await litellm_client.acompletion(
                messages=messages,
                model=model,
                temperature=0.1,
            )
            raw_text = resp["choices"][0]["message"]["content"]
            # Extract JSON block
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data
        except Exception as e:
            logger.warning("structured_comparison_llm_failed", error=str(e))

        # Fallback heuristic structure if LLM json fails
        heuristic_conflicts = self.detect_simple_conflicts(sources_doc_a, sources_doc_b)
        doc_a_name = sources_doc_a[0].document_name if sources_doc_a else "Document A"
        doc_b_name = sources_doc_b[0].document_name if sources_doc_b else "Document B"

        return {
            "summary": f"Comparison between {doc_a_name} and {doc_b_name} regarding '{topic}'.",
            "dimensions": [
                {
                    "dimension": topic,
                    "doc_a_claim": f"{len(sources_doc_a)} passages reviewed from {doc_a_name}",
                    "doc_b_claim": f"{len(sources_doc_b)} passages reviewed from {doc_b_name}",
                    "status": "DIVERGENCE" if heuristic_conflicts else "AGREEMENT",
                    "conflict_severity": "MEDIUM" if heuristic_conflicts else "NONE",
                }
            ],
            "heuristic_conflicts": heuristic_conflicts,
            "key_takeaways": [
                f"{len(sources_doc_a)} sources from {doc_a_name}",
                f"{len(sources_doc_b)} sources from {doc_b_name}",
            ],
        }


source_comparator = SourceComparator()
