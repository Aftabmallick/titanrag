from titan_workers.pipeline.parser.base import DocumentParser
from titan_workers.pipeline.parser.docx_parser import DOCXParser
from titan_workers.pipeline.parser.pdf_parser import PDFParser
from titan_workers.pipeline.parser.table_parser import TableParser
from titan_workers.pipeline.parser.text_parser import TextAndMarkdownParser


def get_parser_for_file(filename: str, mime_type: str = "") -> DocumentParser:
    lower_fn = filename.lower()
    lower_mime = mime_type.lower()

    if lower_fn.endswith(".pdf") or "pdf" in lower_mime:
        return PDFParser()
    elif lower_fn.endswith((".docx", ".doc", ".pptx", ".ppt")) or "officedocument" in lower_mime:
        return DOCXParser()
    elif lower_fn.endswith((".csv", ".tsv")) or "csv" in lower_mime:
        return TableParser()
    else:
        # Default fallback for txt, md, json, html, code, etc.
        return TextAndMarkdownParser()
