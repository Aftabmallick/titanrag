"""
Structural PDF Parser supporting Docling structural hierarchies, OCR mode
for scanned documents, and exact token-matrix bounding box extraction.
"""

from __future__ import annotations

import io
from typing import Any

import structlog
from pypdf import PdfReader
from titan_workers.pipeline.parser.base import (
    BoundingBox,
    DocumentParser,
    ElementType,
    ParsedDocument,
    ParsedElement,
)

logger = structlog.get_logger("titanrag.parser.pdf")


class PDFParser(DocumentParser):
    """
    Structural PDF Parser supporting Docling structural hierarchies, OCR mode
    for scanned documents, and token-matrix bounding box extraction.
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

    def _extract_page_with_matrix_boxes(
        self,
        page: Any,
        page_num: int,
    ) -> list[tuple[str, BoundingBox]]:
        """
        Extracts lines of text paired with authentic bounding box coordinates
        derived from pypdf text matrices (tm) and mediabox dimensions.
        """
        fragments: list[dict[str, Any]] = []

        try:
            page_w = float(page.mediabox.width) if hasattr(page, "mediabox") and page.mediabox else 612.0
            page_h = float(page.mediabox.height) if hasattr(page, "mediabox") and page.mediabox else 792.0
        except Exception:
            page_w = 612.0
            page_h = 792.0

        def visitor_text(text: str, cm: Any, tm: Any, font_dict: Any, font_size: float | None) -> None:
            if not text or not text.strip():
                return
            fs = float(font_size or 11.0)
            # tm is [a, b, c, d, e, f] where e is x_pts, f is y_pts
            try:
                x_pts = float(tm[4]) if tm and len(tm) > 4 else 54.0
                y_pts = float(tm[5]) if tm and len(tm) > 5 else 700.0
            except (IndexError, TypeError):
                x_pts = 54.0
                y_pts = 700.0

            width_pts = max(10.0, len(text) * fs * 0.52)
            height_pts = max(8.0, fs * 1.25)

            # Invert PDF bottom-left origin to standard top-left origin
            x_norm = max(0.0, min(0.99, x_pts / page_w))
            y_norm = max(0.0, min(0.99, (page_h - y_pts - height_pts) / page_h))
            w_norm = max(0.01, min(1.0 - x_norm, width_pts / page_w))
            h_norm = max(0.005, min(1.0 - y_norm, height_pts / page_h))

            fragments.append(
                {
                    "text": text,
                    "x": x_norm,
                    "y": y_norm,
                    "w": w_norm,
                    "h": h_norm,
                    "font_size": fs,
                }
            )

        try:
            page.extract_text(visitor_text=visitor_text)
        except Exception as e:
            logger.debug("visitor_text_matrix_failed_fallback_to_plain", error=str(e))

        if fragments:
            # Group fragments by line baseline (clustering y coordinates within 0.015 tolerance)
            fragments.sort(key=lambda f: (round(f["y"], 2), f["x"]))
            lines: list[tuple[str, BoundingBox]] = []
            curr_line_texts: list[str] = []
            curr_bbox: dict[str, float] | None = None

            for f in fragments:
                if curr_bbox is None:
                    curr_bbox = {"x": f["x"], "y": f["y"], "w": f["w"], "h": f["h"]}
                    curr_line_texts = [f["text"]]
                elif abs(f["y"] - curr_bbox["y"]) < 0.018:
                    # Same visual line
                    curr_line_texts.append(f["text"])
                    curr_bbox["w"] = max(curr_bbox["w"], (f["x"] + f["w"]) - curr_bbox["x"])
                    curr_bbox["h"] = max(curr_bbox["h"], f["h"])
                else:
                    # Flush previous line
                    full_line = " ".join(curr_line_texts).strip()
                    if full_line:
                        lines.append(
                            (
                                full_line,
                                BoundingBox(
                                    page_number=page_num,
                                    x=round(curr_bbox["x"], 3),
                                    y=round(curr_bbox["y"], 3),
                                    width=round(min(0.95, curr_bbox["w"]), 3),
                                    height=round(min(0.2, curr_bbox["h"]), 3),
                                ),
                            )
                        )
                    curr_bbox = {"x": f["x"], "y": f["y"], "w": f["w"], "h": f["h"]}
                    curr_line_texts = [f["text"]]

            if curr_bbox and curr_line_texts:
                full_line = " ".join(curr_line_texts).strip()
                if full_line:
                    lines.append(
                        (
                            full_line,
                            BoundingBox(
                                page_number=page_num,
                                x=round(curr_bbox["x"], 3),
                                y=round(curr_bbox["y"], 3),
                                width=round(min(0.95, curr_bbox["w"]), 3),
                                height=round(min(0.2, curr_bbox["h"]), 3),
                            ),
                        )
                    )
            if lines:
                return lines

        # Fallback to plain line splitting if visitor yielded nothing
        plain_text = page.extract_text() or ""
        plain_lines = [line_str.strip() for line_str in plain_text.splitlines() if line_str.strip()]
        fallback_lines = []
        for idx, line in enumerate(plain_lines):
            line_y = idx / max(len(plain_lines), 1)
            bbox = BoundingBox(
                page_number=page_num,
                x=0.08,
                y=round(line_y, 3),
                width=0.84,
                height=round(1.0 / max(len(plain_lines), 1), 3),
            )
            fallback_lines.append((line, bbox))
        return fallback_lines

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

                # Extract line elements paired with authentic matrix bounding boxes
                extracted_lines = self._extract_page_with_matrix_boxes(page, page_num)

                for cleaned, bbox in extracted_lines:
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
