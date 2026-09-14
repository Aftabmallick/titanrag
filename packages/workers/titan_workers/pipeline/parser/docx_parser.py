import io

import structlog
from docx import Document as DocxReader
from titan_workers.pipeline.parser.base import DocumentParser, ElementType, ParsedDocument, ParsedElement

logger = structlog.get_logger("titanrag.parser.docx")


class DOCXParser(DocumentParser):
    """
    Structural DOCX and Office document parser preserving headings, lists, and tables.
    """

    async def parse(self, file_bytes: bytes, filename: str, mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document") -> ParsedDocument:
        elements: list[ParsedElement] = []
        raw_text_parts: list[str] = []

        try:
            doc = DocxReader(io.BytesIO(file_bytes))
            current_hierarchy: list[str] = []

            # 1. Process paragraphs & headings
            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue

                style_name = (p.style.name or "").lower() if p.style else ""
                if "heading" in style_name or style_name.startswith("title"):
                    el_type = ElementType.HEADING
                    current_hierarchy = [text]
                elif "list" in style_name or text.startswith(("-", "•", "*")):
                    el_type = ElementType.LIST_ITEM
                else:
                    el_type = ElementType.PARAGRAPH

                elements.append(
                    ParsedElement(
                        text=text,
                        element_type=el_type,
                        section_hierarchy=list(current_hierarchy),
                        page_number=1,
                    )
                )
                raw_text_parts.append(text)

            # 2. Process embedded tables as discrete atomic table elements
            for t_idx, table in enumerate(doc.tables):
                rows_data: list[list[str]] = []
                for row in table.rows:
                    row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    rows_data.append(row_cells)

                if rows_data:
                    # Convert to Markdown table
                    header = rows_data[0]
                    md_lines = [
                        "| " + " | ".join(header) + " |",
                        "| " + " | ".join(["---"] * len(header)) + " |",
                    ]
                    for r in rows_data[1:]:
                        md_lines.append("| " + " | ".join(r) + " |")

                    md_table = "\n".join(md_lines)
                    elements.append(
                        ParsedElement(
                            text=md_table,
                            element_type=ElementType.TABLE,
                            section_hierarchy=list(current_hierarchy),
                            page_number=1,
                            meta={"table_index": t_idx, "rows": len(rows_data)},
                        )
                    )
                    raw_text_parts.append(md_table)

            return ParsedDocument(
                elements=elements,
                raw_text="\n\n".join(raw_text_parts),
                meta={"total_elements": len(elements), "parser": "docx_structural"},
            )

        except Exception as e:
            logger.error("docx_parsing_failed", filename=filename, error=str(e))
            raise e
