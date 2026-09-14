import pytest
from titan_workers.pipeline.parser import get_parser_for_file
from titan_workers.pipeline.parser.base import ElementType
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


def test_parser_factory_selection():
    p1 = get_parser_for_file("contract.pdf")
    assert p1.__class__.__name__ == "PDFParser"

    p2 = get_parser_for_file("memo.docx")
    assert p2.__class__.__name__ == "DOCXParser"

    p3 = get_parser_for_file("metrics.csv")
    assert p3.__class__.__name__ == "TableParser"

    p4 = get_parser_for_file("readme.md")
    assert p4.__class__.__name__ == "TextAndMarkdownParser"
