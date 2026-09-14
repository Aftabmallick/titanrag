import io
import zipfile

import pytest
from titan_workers.pipeline.parser import get_parser_for_file
from titan_workers.pipeline.parser.base import ElementType
from titan_workers.pipeline.parser.pdf_parser import PDFParser
from titan_workers.pipeline.parser.pptx_parser import PPTXParser
from titan_workers.pipeline.parser.table_parser import TableParser
from titan_workers.pipeline.parser.text_parser import TextAndMarkdownParser


@pytest.mark.asyncio
async def test_markdown_and_text_parser():
    md_content = """# Executive Summary
This is the executive summary paragraph.

## Financial Performance
Revenue increased by 25% year-over-year.

```python
def compute_growth():
    return 1.25
```

- Key Driver 1: Cloud adoption
- Key Driver 2: International expansion
"""
    parser = TextAndMarkdownParser()
    doc = await parser.parse(md_content.encode("utf-8"), "report.md", "text/markdown")

    assert len(doc.elements) >= 5
    # Headings
    headings = [e for e in doc.elements if e.element_type == ElementType.HEADING]
    assert len(headings) >= 2
    assert headings[0].text == "Executive Summary"
    assert headings[1].text == "Financial Performance"

    # Code block kept intact
    code_elems = [e for e in doc.elements if e.element_type == ElementType.CODE]
    assert len(code_elems) == 1
    assert "def compute_growth" in code_elems[0].text
    assert code_elems[0].meta.get("language") == "python"

    # List items
    list_elems = [e for e in doc.elements if e.element_type == ElementType.LIST_ITEM]
    assert len(list_elems) == 2


@pytest.mark.asyncio
async def test_csv_table_parser():
    csv_content = """Quarter,Revenue,Expenses,Net Income
Q1 2024,100M,60M,40M
Q2 2024,120M,70M,50M
Q3 2024,140M,75M,65M
"""
    parser = TableParser()
    doc = await parser.parse(csv_content.encode("utf-8"), "financials.csv", "text/csv")

    assert len(doc.elements) == 1
    table_elem = doc.elements[0]
    assert table_elem.element_type == ElementType.TABLE
    assert "| Quarter | Revenue | Expenses | Net Income |" in table_elem.text
    assert "| Q1 2024 | 100M | 60M | 40M |" in table_elem.text
    assert "Table containing 3 rows and 4 columns" in table_elem.text


@pytest.mark.asyncio
async def test_pptx_parser_extraction():
    # Build minimal valid XML zip representing PPTX
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
        <p:cSld>
            <p:spTree>
                <p:sp><p:txBody><a:p><a:r><a:t>Quarterly Strategy Review</a:t></a:r></a:p></p:txBody></p:sp>
                <p:sp><p:txBody><a:p><a:r><a:t>Accelerate hybrid search adoption</a:t></a:r></a:p></p:txBody></p:sp>
                <p:sp><p:txBody><a:p><a:r><a:t>Maintain zero-loss transactional outbox</a:t></a:r></a:p></p:txBody></p:sp>
            </p:spTree>
        </p:cSld>
    </p:sld>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide1.xml", slide_xml)
    pptx_bytes = buf.getvalue()

    parser = PPTXParser()
    parsed_doc = await parser.parse(pptx_bytes, "strategy.pptx")

    assert parsed_doc.meta.get("total_slides") == 1
    assert len(parsed_doc.elements) == 3
    assert parsed_doc.elements[0].element_type == ElementType.HEADING
    assert "Slide 1: Quarterly Strategy Review" in parsed_doc.elements[0].text
    assert parsed_doc.elements[1].element_type == ElementType.LIST_ITEM
    assert "Accelerate hybrid search adoption" in parsed_doc.elements[1].text


def test_pdf_ocr_mode_fallback():
    parser = PDFParser(min_text_len_for_ocr=50)
    ocr_elements = parser._ocr_page_fallback(page_num=1, image_bytes=None)
    assert len(ocr_elements) >= 1
    assert ocr_elements[0].meta.get("ocr_applied") is True
    assert ocr_elements[0].page_number == 1
    assert ocr_elements[0].bbox.page_number == 1


def test_parser_factory_selection():
    p1 = get_parser_for_file("contract.pdf")
    assert p1.__class__.__name__ == "PDFParser"

    p2 = get_parser_for_file("memo.docx")
    assert p2.__class__.__name__ == "DOCXParser"

    p3 = get_parser_for_file("deck.pptx")
    assert p3.__class__.__name__ == "PPTXParser"

    p4 = get_parser_for_file("metrics.csv")
    assert p4.__class__.__name__ == "TableParser"

    p5 = get_parser_for_file("readme.md")
    assert p5.__class__.__name__ == "TextAndMarkdownParser"
