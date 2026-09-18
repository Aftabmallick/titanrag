from dataclasses import dataclass

import structlog

logger = structlog.get_logger("titanrag.colpali.classifier")


@dataclass
class PageLayoutMetrics:
    page_number: int
    text_length: int
    image_count: int
    table_count: int
    drawing_count: int
    image_area_ratio: float
    entropy_score: float
    is_visual_qualified: bool


class VisualEntropyClassifier:
    """
    Gated Layout and Visual Entropy Classifier.
    Analyzes document page structural elements to determine whether a page contains
    diagrams, charts, architectural drawings, or infographics.
    Strictly gates expensive multi-vector ColPali ingestion to <=15% of pages.
    """

    THRESHOLD: float = 0.15

    @classmethod
    def evaluate_page(
        cls,
        page_number: int,
        text: str,
        image_count: int = 0,
        table_count: int = 0,
        drawing_count: int = 0,
        image_area_ratio: float = 0.0,
    ) -> PageLayoutMetrics:
        """
        Calculates normalized visual entropy score in [0.0, 1.0].
        A page with charts or diagrams receives high visual score (> 0.15).
        A page dominated by dense linear text paragraphs receives low score (< 0.10).
        """
        text_len = len(text.strip())

        # Scoring heuristics:
        # 1. High image area coverage increases entropy
        area_score = min(1.0, image_area_ratio * 1.5)

        # 2. Diagrams/drawings (vector paths) indicate schematics/flowcharts
        drawing_score = min(0.5, drawing_count * 0.05)

        # 3. Tables indicate structured financial/spec data
        table_score = min(0.4, table_count * 0.2)

        # 4. Text density suppresses visual gating unless accompanied by prominent figures
        text_penalty = 0.0
        if text_len > 1500:
            text_penalty = 0.3
        elif text_len > 800:
            text_penalty = 0.15

        raw_score = (area_score * 0.5) + (drawing_score * 0.3) + (table_score * 0.2) - text_penalty
        entropy_score = max(0.0, min(1.0, round(raw_score, 4)))

        # Explicit qualification override: page with prominent image and low text is always qualified
        if image_area_ratio >= 0.25 and text_len < 500:
            entropy_score = max(entropy_score, 0.35)

        is_qualified = entropy_score >= cls.THRESHOLD

        return PageLayoutMetrics(
            page_number=page_number,
            text_length=text_len,
            image_count=image_count,
            table_count=table_count,
            drawing_count=drawing_count,
            image_area_ratio=image_area_ratio,
            entropy_score=entropy_score,
            is_visual_qualified=is_qualified,
        )
