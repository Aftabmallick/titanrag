import pytest
from titan_workers.pipeline.chunker.contextual import ContextualPrefixEnricher
from titan_workers.pipeline.chunker.hierarchical import HierarchicalChunker
from titan_workers.pipeline.parser.base import ElementType, ParsedDocument, ParsedElement


def test_hierarchical_chunking_with_table_isolation():
    elements = [
        ParsedElement(
            text="First introductory paragraph about the enterprise system architecture.",
            element_type=ElementType.PARAGRAPH,
            section_hierarchy=["Architecture", "Overview"],
            page_number=1,
        ),
        ParsedElement(
            text="| Service | Port | Protocol |\n| --- | --- | --- |\n| Backend | 8000 | HTTP |\n| Qdrant | 6333 | HTTP |",
            element_type=ElementType.TABLE,
            section_hierarchy=["Architecture", "Ports"],
            page_number=1,
        ),
        ParsedElement(
            text="Closing remarks on system deployment parameters and configuration.",
            element_type=ElementType.PARAGRAPH,
            section_hierarchy=["Architecture", "Deployment"],
            page_number=2,
        ),
    ]
    parsed_doc = ParsedDocument(elements=elements, raw_text="")
    chunker = HierarchicalChunker(parent_chunk_tokens=500, child_chunk_tokens=100)
    parents, children = chunker.chunk_document(parsed_doc, "architecture.pdf")

    assert len(parents) >= 1
    assert len(children) >= 3

    # Verify table is isolated as an atomic chunk
    table_children = [c for c in children if c.meta.get("is_atomic") and c.meta.get("type") == "table"]
    assert len(table_children) == 1
    assert "| Backend | 8000 | HTTP |" in table_children[0].content

    # Verify metadata prefix exists
    for child in children:
        assert child.content.startswith("[Doc: architecture.pdf | Section:")
        assert "Page:" in child.content


@pytest.mark.asyncio
async def test_contextual_prefix_enricher():
    elements = [
        ParsedElement(
            text="Section A content regarding fiscal policies.",
            element_type=ElementType.PARAGRAPH,
            section_hierarchy=["Fiscal", "Policies"],
            page_number=1,
        )
    ]
    parsed_doc = ParsedDocument(elements=elements, raw_text="")
    chunker = HierarchicalChunker()
    _, children = chunker.chunk_document(parsed_doc, "policy.txt")

    enricher = ContextualPrefixEnricher(cache_enabled=True)
    enriched = await enricher.enrich_chunks(children)

    assert len(enriched) == len(children)
    assert enriched[0].content.startswith("Context:")
    assert "Fiscal > Policies" in enriched[0].content
