import math
from typing import Any


def calculate_two_proportion_z_test(
    count_a: int,  # Successes in Control
    n_a: int,      # Total in Control
    count_b: int,  # Successes in Treatment
    n_b: int,      # Total in Treatment
) -> dict[str, Any]:
    """Performs a two-proportion Z-test for satisfaction rate difference.

    H0: p_A == p_B
    H1: p_A != p_B
    """
    if n_a <= 0 or n_b <= 0:
        return {
            "p_value": 1.0,
            "z_score": 0.0,
            "statistically_significant": False,
            "rate_a": 0.0,
            "rate_b": 0.0,
        }

    p_a = count_a / n_a
    p_b = count_b / n_b

    # Pooled proportion
    p_pool = (count_a + count_b) / (n_a + n_b)
    if p_pool == 0 or p_pool == 1:
        return {
            "p_value": 1.0,
            "z_score": 0.0,
            "statistically_significant": False,
            "rate_a": p_a,
            "rate_b": p_b,
        }

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return {
            "p_value": 1.0,
            "z_score": 0.0,
            "statistically_significant": False,
            "rate_a": p_a,
            "rate_b": p_b,
        }

    z = (p_b - p_a) / se
    # Two-tailed p-value from standard normal approximation
    p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

    is_significant = p_val < 0.05 and (n_a + n_b >= 30)

    return {
        "p_value": round(float(p_val), 4),
        "z_score": round(float(z), 3),
        "statistically_significant": is_significant,
        "rate_a": round(p_a, 4),
        "rate_b": round(p_b, 4),
        "relative_lift_percent": round(((p_b - p_a) / p_a * 100) if p_a > 0 else 0.0, 2),
    }
