"""FinOps Compute Unit (CU) & Dollar Cost Calculator.

Normalized formula:
CU = 1.0 * (prompt_tokens / 1000)
   + 3.0 * (completion_tokens / 1000)
   + 3.0 * OCR_pages
   + 5.0 * Contextual_windows
   + 10.0 * ColPali_pages
   + 2.0 * Rerank_calls
"""

from decimal import ROUND_HALF_UP, Decimal

# Standard dollar rate per Compute Unit (e.g. $0.002 per CU)
DEFAULT_DOLLAR_PER_CU = 0.0025


def calculate_compute_units(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    ocr_pages: int = 0,
    contextual_windows: int = 0,
    colpali_pages: int = 0,
    rerank_calls: int = 0,
) -> float:
    cu = (
        (1.0 * (prompt_tokens / 1000.0))
        + (3.0 * (completion_tokens / 1000.0))
        + (3.0 * ocr_pages)
        + (5.0 * contextual_windows)
        + (10.0 * colpali_pages)
        + (2.0 * rerank_calls)
    )
    # Round to 4 decimal places
    return float(Decimal(str(cu)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def calculate_dollar_cost(
    compute_units: float,
    rate_per_cu: float = DEFAULT_DOLLAR_PER_CU,
) -> float:
    cost = compute_units * rate_per_cu
    return float(Decimal(str(cost)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
