import csv
import io

import structlog
from titan_workers.pipeline.parser.base import DocumentParser, ElementType, ParsedDocument, ParsedElement

logger = structlog.get_logger("titanrag.parser.table")


class TableParser(DocumentParser):
    """
    Parser for CSV/TSV tabular data.
    Converts tables to aligned Markdown and generates semantic descriptions for embedding quality.
    """

    async def parse(self, file_bytes: bytes, filename: str, mime_type: str = "text/csv") -> ParsedDocument:
        try:
            content = file_bytes.decode("utf-8", errors="replace")
            delimiter = "\t" if filename.endswith(".tsv") or "\t" in content[:200] else ","

            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            rows = [row for row in reader if any(cell.strip() for cell in row)]

            if not rows:
                return ParsedDocument(elements=[], raw_text="", meta={"rows": 0})

            header = rows[0]
            data_rows = rows[1:]

            # Construct clean aligned Markdown table
            md_lines = [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join(["---"] * len(header)) + " |",
            ]
            for row in data_rows:
                # Pad row to header length if shorter
                padded_row = row + [""] * (len(header) - len(row))
                md_lines.append("| " + " | ".join(padded_row[: len(header)]) + " |")

            md_table = "\n".join(md_lines)

            # Generate natural language semantic description for retrieval quality
            col_names = ", ".join([f"'{c.strip()}'" for c in header if c.strip()])
            nl_description = (
                f"Table containing {len(data_rows)} rows and {len(header)} columns. "
                f"Columns include: {col_names}."
            )

            element = ParsedElement(
                text=f"{nl_description}\n\n{md_table}",
                element_type=ElementType.TABLE,
                section_hierarchy=[f"Table: {filename}"],
                page_number=1,
                meta={
                    "total_rows": len(data_rows),
                    "columns": header,
                    "table_description": nl_description,
                },
            )

            return ParsedDocument(
                elements=[element],
                raw_text=md_table,
                meta={
                    "total_rows": len(data_rows),
                    "total_columns": len(header),
                    "parser": "table_csv",
                },
            )

        except Exception as e:
            logger.error("table_parsing_failed", filename=filename, error=str(e))
            raise e
