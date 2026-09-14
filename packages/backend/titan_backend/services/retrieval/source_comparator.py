from titan_backend.services.retrieval.context_packer import PackedSource

COMPARISON_SYSTEM_PROMPT = """You are TitanRAG operating in Source Comparison Mode.
Your task is to compare and contrast how the provided documents address the specified topic.
Requirements:
1. Provide a side-by-side comparative table summarizing the key differences and agreements.
2. Follow the table with a detailed comparative narrative.
3. Every claim MUST be explicitly cited with [Source N].
"""


class SourceComparator:
    """Orchestrates structured document comparison and side-by-side synthesis."""

    def format_comparison_prompt(
        self, sources_doc_a: list[PackedSource], sources_doc_b: list[PackedSource], topic: str
    ) -> str:
        all_sources = sources_doc_a + sources_doc_b
        src_blocks = []
        for s in all_sources:
            src_blocks.append(f"[Source {s.source_index}] (Doc: {s.document_name}, Page: {s.page_number}):\n{s.text}\n")

        joined_sources = "\n".join(src_blocks)
        return (
            f"{COMPARISON_SYSTEM_PROMPT}\n\n"
            f"=== TOPIC TO COMPARE ===\n{topic}\n\n"
            f"=== EXTRACTED SOURCES ===\n{joined_sources}\n"
        )


source_comparator = SourceComparator()
