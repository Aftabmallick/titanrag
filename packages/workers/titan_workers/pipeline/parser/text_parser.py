import re

import structlog
from titan_workers.pipeline.parser.base import DocumentParser, ElementType, ParsedDocument, ParsedElement

logger = structlog.get_logger("titanrag.parser.text")


class TextAndMarkdownParser(DocumentParser):
    """
    Parser for Markdown and plain text documents.
    Preserves heading hierarchies, frontmatter metadata, and code blocks.
    """

    async def parse(self, file_bytes: bytes, filename: str, mime_type: str = "text/markdown") -> ParsedDocument:
        elements: list[ParsedElement] = []
        try:
            content = file_bytes.decode("utf-8", errors="replace")
            lines = content.splitlines()

            in_code_block = False
            current_code_lines: list[str] = []
            code_lang = ""
            current_hierarchy: list[str] = []

            for _line_idx, line in enumerate(lines):
                # Check for fenced code block toggle
                if line.strip().startswith("```"):
                    if in_code_block:
                        # End of code block
                        current_code_lines.append(line)
                        full_code = "\n".join(current_code_lines)
                        elements.append(
                            ParsedElement(
                                text=full_code,
                                element_type=ElementType.CODE,
                                section_hierarchy=list(current_hierarchy),
                                page_number=1,
                                meta={"language": code_lang},
                            )
                        )
                        in_code_block = False
                        current_code_lines = []
                        code_lang = ""
                        continue
                    else:
                        # Start of code block
                        in_code_block = True
                        code_lang = line.strip().lstrip("`").strip()
                        current_code_lines = [line]
                        continue

                if in_code_block:
                    current_code_lines.append(line)
                    continue

                stripped = line.strip()
                if not stripped:
                    continue

                # Heading detection (#, ##, ###)
                heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
                if heading_match:
                    level = len(heading_match.group(1))
                    heading_text = heading_match.group(2)
                    # Adjust hierarchy
                    if len(current_hierarchy) >= level:
                        current_hierarchy = current_hierarchy[: level - 1]
                    current_hierarchy.append(heading_text)

                    elements.append(
                        ParsedElement(
                            text=heading_text,
                            element_type=ElementType.HEADING,
                            section_hierarchy=list(current_hierarchy),
                            page_number=1,
                            meta={"level": level},
                        )
                    )
                elif stripped.startswith(("-", "*", "+")) or re.match(r"^\d+\.\s", stripped):
                    elements.append(
                        ParsedElement(
                            text=stripped,
                            element_type=ElementType.LIST_ITEM,
                            section_hierarchy=list(current_hierarchy),
                            page_number=1,
                        )
                    )
                else:
                    elements.append(
                        ParsedElement(
                            text=stripped,
                            element_type=ElementType.PARAGRAPH,
                            section_hierarchy=list(current_hierarchy),
                            page_number=1,
                        )
                    )

            # If EOF inside code block
            if in_code_block and current_code_lines:
                elements.append(
                    ParsedElement(
                        text="\n".join(current_code_lines),
                        element_type=ElementType.CODE,
                        section_hierarchy=list(current_hierarchy),
                        page_number=1,
                        meta={"language": code_lang},
                    )
                )

            return ParsedDocument(
                elements=elements,
                raw_text=content,
                meta={"total_elements": len(elements), "parser": "markdown_structural"},
            )

        except Exception as e:
            logger.error("text_parsing_failed", filename=filename, error=str(e))
            raise e
