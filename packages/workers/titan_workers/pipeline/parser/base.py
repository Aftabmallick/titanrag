import enum
from dataclasses import dataclass, field
from typing import Any, Protocol


class ElementType(str, enum.Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE = "code"
    LIST_ITEM = "list_item"
    IMAGE = "image"
    METADATA = "metadata"


@dataclass
class BoundingBox:
    page_number: int
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class ParsedElement:
    text: str
    element_type: ElementType
    section_hierarchy: list[str] = field(default_factory=list)
    page_number: int | None = None
    bbox: BoundingBox | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    elements: list[ParsedElement]
    raw_text: str
    meta: dict[str, Any] = field(default_factory=dict)


class DocumentParser(Protocol):
    async def parse(self, file_bytes: bytes, filename: str, mime_type: str) -> ParsedDocument: ...
