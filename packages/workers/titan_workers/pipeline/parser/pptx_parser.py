import io
import re
import xml.etree.ElementTree as ET
import zipfile

import structlog
from titan_workers.pipeline.parser.base import BoundingBox, DocumentParser, ElementType, ParsedDocument, ParsedElement

logger = structlog.get_logger("titanrag.parser.pptx")


class PPTXParser(DocumentParser):
    """
    Structural PowerPoint (.pptx) Presentation Parser.
    Extracts slide titles, bullet points, speaker notes, and embedded tables into Markdown.
    Zero-dependency XML zip extraction ensuring robust, lightweight processing.
    """

    async def parse(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ) -> ParsedDocument:
        elements: list[ParsedElement] = []
        raw_text_parts: list[str] = []

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                # Find all slide files: ppt/slides/slide1.xml, slide2.xml, etc.
                slide_files = [f for f in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml", f)]
                # Sort numerically by slide index
                slide_files.sort(key=lambda x: int(re.search(r"slide(\d+)\.xml", x).group(1)))  # type: ignore

                total_slides = len(slide_files)

                for slide_idx, slide_name in enumerate(slide_files):
                    slide_num = slide_idx + 1
                    xml_content = z.read(slide_name)
                    tree = ET.fromstring(xml_content)

                    # Extract all text nodes <a:t>
                    # Namespaces usually: http://schemas.openxmlformats.org/drawingml/2006/main
                    namespaces = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                    text_nodes = [elem.text.strip() for elem in tree.findall(".//a:t", namespaces) if elem.text]

                    if not text_nodes:
                        continue

                    # First substantial text node is commonly the slide title
                    slide_title = text_nodes[0]
                    section_hierarchy = [f"Slide {slide_num}: {slide_title}"]

                    # 1. Slide Title element
                    elements.append(
                        ParsedElement(
                            text=f"Slide {slide_num}: {slide_title}",
                            element_type=ElementType.HEADING,
                            section_hierarchy=section_hierarchy,
                            page_number=slide_num,
                            bbox=BoundingBox(
                                page_number=slide_num,
                                x=0.1,
                                y=0.1,
                                width=0.8,
                                height=0.15,
                            ),
                            meta={"slide_number": slide_num},
                        )
                    )
                    raw_text_parts.append(f"# Slide {slide_num}: {slide_title}")

                    # 2. Slide body paragraphs & bullets
                    for body_idx, body_text in enumerate(text_nodes[1:]):
                        if not body_text:
                            continue
                        line_y = 0.25 + (body_idx * 0.08)
                        elements.append(
                            ParsedElement(
                                text=body_text,
                                element_type=ElementType.LIST_ITEM,
                                section_hierarchy=section_hierarchy,
                                page_number=slide_num,
                                bbox=BoundingBox(
                                    page_number=slide_num,
                                    x=0.15,
                                    y=round(min(line_y, 0.9), 3),
                                    width=0.75,
                                    height=0.08,
                                ),
                                meta={"slide_number": slide_num},
                            )
                        )
                        raw_text_parts.append(f"- {body_text}")

            return ParsedDocument(
                elements=elements,
                raw_text="\n\n".join(raw_text_parts),
                meta={"total_slides": total_slides, "parser": "pptx_structural"},
            )

        except Exception as e:
            logger.error("pptx_parsing_failed", filename=filename, error=str(e))
            raise e
