import math
from typing import Any

try:
    import scipy.stats as stats

    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


def calculate_two_proportion_z_test(
    count_a: int,  # Successes in Control
    n_a: int,  # Total in Control
    count_b: int,  # Successes in Treatment
    n_b: int,  # Total in Treatment
) -> dict[str, Any]:
    """Performs a two-proportion Z-test for satisfaction/conversion rate difference.

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
            "relative_lift_percent": 0.0,
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
            "relative_lift_percent": 0.0,
        }

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return {
            "p_value": 1.0,
            "z_score": 0.0,
            "statistically_significant": False,
            "rate_a": p_a,
            "rate_b": p_b,
            "relative_lift_percent": 0.0,
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


def calculate_welch_t_test(
    mean_a: float,
    std_a: float,
    n_a: int,
    mean_b: float,
    std_b: float,
    n_b: int,
) -> dict[str, Any]:
    """Performs Welch's t-test for two independent samples with unequal variances.

    Ideal for continuous RAG metrics: latency (ms), token count, CU cost, or retrieval similarity.
    H0: mu_A == mu_B
    H1: mu_A != mu_B
    """
    if n_a < 2 or n_b < 2:
        return {
            "t_statistic": 0.0,
            "p_value": 1.0,
            "degrees_of_freedom": 0.0,
            "statistically_significant": False,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "relative_change_percent": 0.0,
        }

    var_a = std_a**2
    var_b = std_b**2

    denom = math.sqrt((var_a / n_a) + (var_b / n_b))
    if denom == 0.0:
        return {
            "t_statistic": 0.0,
            "p_value": 1.0,
            "degrees_of_freedom": 0.0,
            "statistically_significant": False,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "relative_change_percent": 0.0,
        }

    t_stat = (mean_b - mean_a) / denom

    # Welch-Satterthwaite degrees of freedom
    term_a = var_a / n_a
    term_b = var_b / n_b
    numerator = (term_a + term_b) ** 2
    denominator = ((term_a**2) / (n_a - 1)) + ((term_b**2) / (n_b - 1))
    df = numerator / denominator if denominator > 0 else 1.0

    if _HAS_SCIPY:
        p_val = float(stats.t.sf(abs(t_stat), df) * 2)
    else:
        p_val = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / math.sqrt(2))))

    is_significant = p_val < 0.05 and (n_a + n_b >= 30)
    rel_change = round(((mean_b - mean_a) / mean_a * 100) if mean_a != 0 else 0.0, 2)

    return {
        "t_statistic": round(float(t_stat), 4),
        "p_value": round(float(p_val), 4),
        "degrees_of_freedom": round(float(df), 2),
        "statistically_significant": is_significant,
        "mean_a": round(mean_a, 4),
        "mean_b": round(mean_b, 4),
        "relative_change_percent": rel_change,
    }


def evaluate_safety_circuit_breaker(
    treatment_error_rate: float,
    control_error_rate: float = 0.0,
    treatment_latency_p95: float | None = None,
    control_latency_p95: float | None = None,
    satisfaction_p_val: float | None = None,
    satisfaction_lift: float | None = None,
    min_treatment_samples: int = 20,
    total_samples: int = 20,
) -> tuple[bool, str | None]:
    """Safety Circuit Breaker: Evaluates whether an active A/B experiment variant

    has introduced severe degradation requiring automatic circuit breaker trip.

    Conditions that trigger a trip:
    1. Treatment error rate >= 5% (0.05) AND at least 2x control error rate.
    2. Severe latency regression: P95 latency is > 2x control latency (if latency > 1000ms).
    3. Severe satisfaction crash: Relative lift <= -25% with statistical significance (p < 0.05).

    Returns:
        (should_trip: bool, trip_reason: str | None)
    """
    if total_samples < min_treatment_samples:
        return False, None

    # Condition 1: Error rate spike
    if treatment_error_rate >= 0.05 and treatment_error_rate > (control_error_rate * 2.0):
        return True, (
            f"Circuit breaker tripped: Treatment error rate spiked to {treatment_error_rate * 100:.1f}% "
            f"(control was {control_error_rate * 100:.1f}%)."
        )

    # Condition 2: Latency regression
    if (
        treatment_latency_p95 is not None
        and control_latency_p95 is not None
        and control_latency_p95 > 0
        and treatment_latency_p95 > 1000
    ):
        if treatment_latency_p95 > (control_latency_p95 * 2.0):
            return True, (
                f"Circuit breaker tripped: Treatment P95 latency degraded to {treatment_latency_p95:.0f}ms "
                f"(>2x control {control_latency_p95:.0f}ms)."
            )

    # Condition 3: Statistically significant negative satisfaction plunge
    if (
        satisfaction_lift is not None
        and satisfaction_lift <= -25.0
        and satisfaction_p_val is not None
        and satisfaction_p_val < 0.05
    ):
        return True, (
            f"Circuit breaker tripped: Statistically significant satisfaction degradation "
            f"({satisfaction_lift:.1f}%, p={satisfaction_p_val:.4f})."
        )

    return False, None
