import re

from titan_backend.api.v1.schemas.chat import CitationPayload
from titan_backend.services.retrieval.context_packer import PackedSource

SOURCE_PATTERN = re.compile(r"\[(?:Source\s*(\d+)|\^(\d+))\]", re.IGNORECASE)


class CitationExtractor:
    """Parses citation tags [Source N] or [^N] from model output and links them to packed source metadata."""

    def extract_citations(self, text: str, sources: list[PackedSource]) -> list[CitationPayload]:
        if not text or not sources:
            return []

        source_map: dict[int, PackedSource] = {s.source_index: s for s in sources}
        found_indices: set[int] = set()

        for match in SOURCE_PATTERN.finditer(text):
            idx_str = match.group(1) or match.group(2)
            if idx_str:
                try:
                    idx = int(idx_str)
                    if idx in source_map:
                        found_indices.add(idx)
                except ValueError:
                    continue

        citations: list[CitationPayload] = []
        for idx in sorted(found_indices):
            s = source_map[idx]
            snippet = s.text[:240].replace("\n", " ")
            if len(s.text) > 240:
                snippet += "..."

            citations.append(
                CitationPayload(
                    source_index=s.source_index,
                    document_id=s.document_id,
                    document_name=s.document_name,
                    chunk_id=s.chunk_id,
                    page_number=s.page_number,
                    bbox=s.bbox,
                    snippet=snippet,
                    relevance_score=round(s.relevance_score, 4),
                    verified=False,
                )
            )

        return citations


citation_extractor = CitationExtractor()
