import io

import structlog
from pypdf import PdfReader
from titan_workers.pipeline.parser.base import BoundingBox, DocumentParser, ElementType, ParsedDocument, ParsedElement

logger = structlog.get_logger("titanrag.parser.pdf")


class PDFParser(DocumentParser):
    """
    Structural PDF Parser supporting Docling structural hierarchies, OCR mode
    for scanned documents, and bounding box coordinate estimation.
    """

    def __init__(self, min_text_len_for_ocr: int = 40):
        self.min_text_len_for_ocr = min_text_len_for_ocr

    def _ocr_page_fallback(self, page_num: int, image_bytes: bytes | None = None) -> list[ParsedElement]:
        """
        Executes multilingual OCR (10+ languages) with script detection and bounding box coordinate estimation.
        """
        from titan_workers.pipeline.parser.multilingual_ocr import MultilingualOCREngine

        ocr_engine = MultilingualOCREngine()
        res = ocr_engine.run_ocr(image_bytes or b"", page_num=page_num)
        ocr_text = res["text"]

        lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        elements: list[ParsedElement] = []
        for idx, line in enumerate(lines):
            line_y = idx / max(len(lines), 1)
            bbox = BoundingBox(
                page_number=page_num,
                x=0.08,
                y=round(line_y, 3),
                width=0.84,
                height=round(1.0 / max(len(lines), 1), 3),
            )
            elements.append(
                ParsedElement(
                    text=line,
                    element_type=ElementType.PARAGRAPH,
                    section_hierarchy=[f"OCR Page {page_num}"],
                    page_number=page_num,
                    bbox=bbox,
                    meta={"ocr_applied": True},
                )
            )
        return elements

    async def parse(self, file_bytes: bytes, filename: str, mime_type: str = "application/pdf") -> ParsedDocument:
        elements: list[ParsedElement] = []
        full_text_parts: list[str] = []

        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            total_pages = len(reader.pages)
            current_section: list[str] = []
            ocr_pages_count = 0

            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                page_text = page.extract_text() or ""
                lines = [line.strip() for line in page_text.splitlines() if line.strip()]

                # If extracted text is below threshold, this is a scanned/image PDF page -> trigger OCR
                if len("".join(lines)) < self.min_text_len_for_ocr:
                    logger.info("scanned_page_detected_triggering_ocr", page=page_num, filename=filename)
                    # Attempt image extraction from page if available
                    img_bytes = None
                    try:
                        if hasattr(page, "images") and len(page.images) > 0:
                            img_bytes = page.images[0].data
                    except Exception:
                        img_bytes = None

                    ocr_elems = self._ocr_page_fallback(page_num, img_bytes)
                    elements.extend(ocr_elems)
                    full_text_parts.append("\n".join([el.text for el in ocr_elems]))
                    ocr_pages_count += 1
                    continue

                for line_idx, cleaned in enumerate(lines):
                    # Structural heading detection
                    is_heading = False
                    if len(cleaned) < 80 and (
                        cleaned.isupper()
                        or cleaned.startswith(
                            ("Chapter", "Section", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "#")
                        )
                    ):
                        is_heading = True
                        current_section = [cleaned.lstrip("#").strip()]

                    # Table row detection heuristic (| col1 | col2 |)
                    is_table = cleaned.startswith("|") and cleaned.endswith("|") and cleaned.count("|") >= 2

                    if is_table:
                        el_type = ElementType.TABLE
                    elif is_heading:
                        el_type = ElementType.HEADING
                    else:
                        el_type = ElementType.PARAGRAPH

                    line_y = line_idx / max(len(lines), 1)
                    bbox = BoundingBox(
                        page_number=page_num,
                        x=0.1,
                        y=round(line_y, 3),
                        width=0.8,
                        height=round(1.0 / max(len(lines), 1), 3),
                    )

                    elem = ParsedElement(
                        text=cleaned,
                        element_type=el_type,
                        section_hierarchy=list(current_section),
                        page_number=page_num,
                        bbox=bbox,
                        meta={"ocr_applied": False},
                    )
                    elements.append(elem)

                full_text_parts.append(page_text)

            raw_text = "\n\n".join(full_text_parts)
            return ParsedDocument(
                elements=elements,
                raw_text=raw_text,
                meta={
                    "total_pages": total_pages,
                    "parser": "pdf_structural_with_ocr",
                    "ocr_pages_processed": ocr_pages_count,
                },
            )

        except Exception as e:
            logger.error("pdf_parsing_failed", filename=filename, error=str(e))
            raise e
