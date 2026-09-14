import uuid
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import structlog
import tiktoken
from titan_workers.pipeline.parser.base import ElementType, ParsedDocument, ParsedElement

logger = structlog.get_logger("titanrag.chunker.hierarchical")


@dataclass
class ChunkOutput:
    id: UUID
    parent_chunk_id: UUID | None
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None
    bbox: dict[str, Any] | None
    section_hierarchy: list[str]
    is_parent: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


class HierarchicalChunker:
    """
    Hierarchical Parent-Child Chunker:
    - Parent chunks: 1024-2048 tokens capturing broader macro context
    - Child chunks: 256 tokens (32 overlap) for high-precision retrieval
    - Table & Code isolation: tables and code blocks are NEVER split across chunks
    - Metadata enrichment prefix: [Doc: {filename} | Section: {hierarchy} | Page: {page}]
    """

    def __init__(
        self,
        parent_chunk_tokens: int = 1024,
        child_chunk_tokens: int = 256,
        overlap_tokens: int = 32,
        model_name: str = "cl100k_base",
    ):
        self.parent_chunk_tokens = parent_chunk_tokens
        self.child_chunk_tokens = child_chunk_tokens
        self.overlap_tokens = overlap_tokens
        try:
            self.tokenizer = tiktoken.get_encoding(model_name)
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _format_prefix(self, filename: str, hierarchy: list[str], page_num: int | None) -> str:
        section_str = " > ".join(hierarchy) if hierarchy else "Overview"
        page_str = str(page_num) if page_num else "1"
        return f"[Doc: {filename} | Section: {section_str} | Page: {page_str}]\n"

    def chunk_document(self, parsed_doc: ParsedDocument, filename: str) -> tuple[list[ChunkOutput], list[ChunkOutput]]:
        """
        Returns: (parent_chunks, child_chunks)
        """
        parent_chunks: list[ChunkOutput] = []
        child_chunks: list[ChunkOutput] = []

        elements = parsed_doc.elements
        if not elements:
            return parent_chunks, child_chunks

        current_parent_elements: list[ParsedElement] = []
        current_parent_tokens = 0
        chunk_idx = 0

        # Helper to flush a parent and generate its constituent child chunks
        def flush_parent(p_elems: list[ParsedElement]) -> None:
            nonlocal chunk_idx
            if not p_elems:
                return

            parent_id = uuid.uuid4()
            combined_text = "\n\n".join([el.text for el in p_elems])
            p_tokens = self.count_tokens(combined_text)
            first_page = p_elems[0].page_number
            p_hierarchy = p_elems[0].section_hierarchy

            p_chunk = ChunkOutput(
                id=parent_id,
                parent_chunk_id=None,
                chunk_index=chunk_idx,
                content=combined_text,
                token_count=p_tokens,
                page_number=first_page,
                bbox=p_elems[0].bbox.to_dict() if p_elems[0].bbox else None,
                section_hierarchy=p_hierarchy,
                is_parent=True,
            )
            parent_chunks.append(p_chunk)
            chunk_idx += 1

            # Now create high-precision child chunks from this parent
            for elem in p_elems:
                prefix = self._format_prefix(filename, elem.section_hierarchy, elem.page_number)
                prefix_tokens = self.count_tokens(prefix)

                # Tables and code blocks are strictly atomic chunks
                if elem.element_type in (ElementType.TABLE, ElementType.CODE):
                    c_id = uuid.uuid4()
                    full_content = prefix + elem.text
                    c_tokens = prefix_tokens + self.count_tokens(elem.text)
                    child_chunks.append(
                        ChunkOutput(
                            id=c_id,
                            parent_chunk_id=parent_id,
                            chunk_index=chunk_idx,
                            content=full_content,
                            token_count=c_tokens,
                            page_number=elem.page_number,
                            bbox=elem.bbox.to_dict() if elem.bbox else None,
                            section_hierarchy=elem.section_hierarchy,
                            is_parent=False,
                            meta={"is_atomic": True, "type": elem.element_type.value},
                        )
                    )
                    chunk_idx += 1
                    continue

                # Standard prose text: split into sliding windows of 256 tokens with 32 overlap
                elem_tokens = self.tokenizer.encode(elem.text)
                if len(elem_tokens) <= self.child_chunk_tokens:
                    c_id = uuid.uuid4()
                    child_chunks.append(
                        ChunkOutput(
                            id=c_id,
                            parent_chunk_id=parent_id,
                            chunk_index=chunk_idx,
                            content=prefix + elem.text,
                            token_count=prefix_tokens + len(elem_tokens),
                            page_number=elem.page_number,
                            bbox=elem.bbox.to_dict() if elem.bbox else None,
                            section_hierarchy=elem.section_hierarchy,
                            is_parent=False,
                        )
                    )
                    chunk_idx += 1
                else:
                    # Multi-window sliding chunking
                    step = max(self.child_chunk_tokens - self.overlap_tokens, 1)
                    for start_i in range(0, len(elem_tokens), step):
                        window = elem_tokens[start_i : start_i + self.child_chunk_tokens]
                        if not window:
                            break
                        c_text = self.tokenizer.decode(window)
                        c_id = uuid.uuid4()
                        child_chunks.append(
                            ChunkOutput(
                                id=c_id,
                                parent_chunk_id=parent_id,
                                chunk_index=chunk_idx,
                                content=prefix + c_text,
                                token_count=prefix_tokens + len(window),
                                page_number=elem.page_number,
                                bbox=elem.bbox.to_dict() if elem.bbox else None,
                                section_hierarchy=elem.section_hierarchy,
                                is_parent=False,
                            )
                        )
                        chunk_idx += 1

        for elem in elements:
            el_tokens = self.count_tokens(elem.text)
            # If element is an atomic table/code, or exceeds parent bound, flush current parent
            if elem.element_type in (ElementType.TABLE, ElementType.CODE):
                if current_parent_elements:
                    flush_parent(current_parent_elements)
                    current_parent_elements = []
                    current_parent_tokens = 0
                flush_parent([elem])
                continue

            if current_parent_tokens + el_tokens > self.parent_chunk_tokens and current_parent_elements:
                flush_parent(current_parent_elements)
                current_parent_elements = [elem]
                current_parent_tokens = el_tokens
            else:
                current_parent_elements.append(elem)
                current_parent_tokens += el_tokens

        if current_parent_elements:
            flush_parent(current_parent_elements)

        return parent_chunks, child_chunks
