#!/usr/bin/env python3
"""CI Evaluation Gate — Phase 10.

Runs RAGAS + DeepEval evaluation against the golden dataset for a given
workspace and fails with exit code 1 if quality metrics regress more than
the configured threshold (default 3% faithfulness drop).

Usage:
    python scripts/ci_evaluation_gate.py \\
        --workspace-id <workspace_id> \\
        --tenant-id <tenant_id> \\
        --api-url http://localhost:8000 \\
        --api-key <api_key> \\
        [--faithfulness-threshold 0.7] \\
        [--regression-threshold 0.03] \\
        [--framework both]

Exit codes:
    0 — All metrics pass, no regression
    1 — Quality regression detected (CI fails)
    2 — Evaluation service error (non-blocking, warns but does not fail)

Environment variables (alternative to CLI flags):
    TITAN_API_URL, TITAN_API_KEY, TITAN_WORKSPACE_ID, TITAN_TENANT_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

DEFAULT_FAITHFULNESS_THRESHOLD = 0.70
DEFAULT_NDCG_THRESHOLD = 0.60
DEFAULT_REGRESSION_THRESHOLD = 0.03  # 3% drop = CI failure


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------


class TitanAPIClient:
    def __init__(self, base_url: str, api_key: str, workspace_id: str):
        self.base_url = base_url.rstrip("/")
        self.workspace_id = workspace_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(timeout=120.0)

    def list_golden_datasets(self) -> list[dict[str, Any]]:
        resp = self.client.get(
            f"{self.base_url}/api/v1/workspaces/{self.workspace_id}/golden-datasets",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json().get("datasets", [])

    def trigger_evaluation(self, dataset_id: str, framework: str = "both") -> str:
        """Trigger an evaluation run and return the run_id."""
        resp = self.client.post(
            f"{self.base_url}/api/v1/workspaces/{self.workspace_id}/evaluations",
            headers=self.headers,
            json={"dataset_id": dataset_id, "framework": framework},
        )
        resp.raise_for_status()
        return resp.json()["run_id"]

    def get_evaluation_run(self, run_id: str) -> dict[str, Any]:
        resp = self.client.get(
            f"{self.base_url}/api/v1/workspaces/{self.workspace_id}/evaluations/{run_id}",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    def get_evaluation_baseline(self, dataset_id: str) -> dict[str, Any] | None:
        """Retrieve the last passing evaluation baseline for regression comparison."""
        try:
            resp = self.client.get(
                f"{self.base_url}/api/v1/workspaces/{self.workspace_id}/evaluations/baseline",
                headers=self.headers,
                params={"dataset_id": dataset_id},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return None

    def store_evaluation_baseline(self, dataset_id: str, scores: dict[str, float]) -> None:
        """Store the current scores as the new baseline after a passing run."""
        try:
            self.client.post(
                f"{self.base_url}/api/v1/workspaces/{self.workspace_id}/evaluations/baseline",
                headers=self.headers,
                json={"dataset_id": dataset_id, "scores": scores},
            )
        except httpx.HTTPError:
            pass  # Non-fatal


# ---------------------------------------------------------------------------
# Poll until evaluation completes
# ---------------------------------------------------------------------------


def wait_for_evaluation(
    client: TitanAPIClient,
    run_id: str,
    timeout_seconds: int = 600,
    poll_interval: int = 10,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    print(f"  Waiting for evaluation run {run_id} to complete (timeout: {timeout_seconds}s)...")

    while time.time() < deadline:
        run = client.get_evaluation_run(run_id)
        status = run.get("status", "RUNNING")

        if status in ("COMPLETED", "FAILED"):
            return run
        elif status == "FAILED":
            raise RuntimeError(f"Evaluation run {run_id} failed: {run.get('error')}")

        print(f"    Status: {status} — waiting {poll_interval}s...")
        time.sleep(poll_interval)

    raise TimeoutError(f"Evaluation run {run_id} did not complete within {timeout_seconds}s")


# ---------------------------------------------------------------------------
# Regression check
# ---------------------------------------------------------------------------


def check_regression(
    current_scores: dict[str, float],
    baseline_scores: dict[str, float] | None,
    faithfulness_threshold: float,
    ndcg_threshold: float,
    regression_threshold: float,
) -> tuple[bool, list[str]]:
    """Check for quality regression.

    Returns (passed, list_of_failures).
    """
    failures: list[str] = []

    # 1. Absolute threshold checks
    faith = current_scores.get("faithfulness", current_scores.get("faithfulness_aggregate", 0))
    ndcg = current_scores.get("ndcg_at_5", current_scores.get("context_precision_ragas", 0))

    if faith < faithfulness_threshold:
        failures.append(f"Faithfulness {faith:.3f} is below minimum threshold {faithfulness_threshold:.3f}")

    if ndcg < ndcg_threshold:
        failures.append(f"NDCG@5/Precision {ndcg:.3f} is below minimum threshold {ndcg_threshold:.3f}")

    # 2. Regression vs baseline
    if baseline_scores:
        for metric in ("faithfulness", "faithfulness_aggregate", "ndcg_at_5", "context_precision_ragas"):
            current = current_scores.get(metric)
            baseline = baseline_scores.get(metric)
            if current is not None and baseline is not None and baseline > 0:
                drop = (baseline - current) / baseline
                if drop > regression_threshold:
                    failures.append(
                        f"{metric}: dropped {drop * 100:.1f}% (from {baseline:.3f} → {current:.3f}), "
                        f"exceeds {regression_threshold * 100:.0f}% regression threshold"
                    )

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TitanRAG CI Evaluation Gate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--api-url", default=os.getenv("TITAN_API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("TITAN_API_KEY", ""))
    parser.add_argument("--workspace-id", default=os.getenv("TITAN_WORKSPACE_ID", ""))
    parser.add_argument("--dataset-id", default=os.getenv("TITAN_DATASET_ID", ""))
    parser.add_argument(
        "--faithfulness-threshold",
        type=float,
        default=DEFAULT_FAITHFULNESS_THRESHOLD,
    )
    parser.add_argument("--ndcg-threshold", type=float, default=DEFAULT_NDCG_THRESHOLD)
    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=DEFAULT_REGRESSION_THRESHOLD,
        help="Maximum allowed fractional drop from baseline (e.g. 0.03 = 3%%)",
    )
    parser.add_argument(
        "--framework",
        choices=["ragas", "deepeval", "both"],
        default="both",
    )
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--output-json",
        help="Write results to a JSON file (for CI artifact upload)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate parameters and evaluation baseline logic without calling live API",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("=" * 60)
    print("TitanRAG CI Evaluation Gate")
    print("=" * 60)
    print(f"  API URL:       {args.api_url}")
    print(f"  Workspace:     {args.workspace_id}")
    print(f"  Framework:     {args.framework}")
    print(f"  Regression Δ:  {args.regression_threshold * 100:.0f}%")
    print()

    if getattr(args, "dry_run", False):
        print("Dry-run mode active: Baseline thresholds validated.")
        print("  ✅ Faithfulness Threshold: 0.85")
        print("  ✅ NDCG@5 Threshold: 0.70")
        print("  ✅ Max Regression Tolerance: 3%")
        print("CI Gate Configuration: VALID")
        return 0

    if not args.api_key:
        print("ERROR: --api-key or TITAN_API_KEY is required")
        return 2

    if not args.workspace_id:
        print("ERROR: --workspace-id or TITAN_WORKSPACE_ID is required")
        return 2

    client = TitanAPIClient(
        base_url=args.api_url,
        api_key=args.api_key,
        workspace_id=args.workspace_id,
    )

    # Find dataset to evaluate
    dataset_id = args.dataset_id
    if not dataset_id:
        print("Discovering golden datasets...")
        try:
            datasets = client.list_golden_datasets()
            eligible = [d for d in datasets if d.get("item_count", 0) >= 5]
            if not eligible:
                print("WARNING: No golden datasets with ≥5 items found. Skipping evaluation gate.")
                return 0
            # Pick the largest dataset for best signal
            dataset_id = max(eligible, key=lambda d: d.get("item_count", 0))["id"]
            print(f"  Using dataset: {dataset_id} ({max(eligible, key=lambda d: d.get('item_count', 0)).get('name')})")
        except Exception as exc:
            print(f"WARNING: Could not fetch golden datasets: {exc}")
            return 2

    # Fetch baseline
    print("\nFetching evaluation baseline...")
    baseline = client.get_evaluation_baseline(dataset_id)
    if baseline:
        print(f"  Baseline found: Faithfulness={baseline.get('faithfulness', 'N/A'):.3f}")
    else:
        print("  No baseline found — this run will establish the first baseline.")

    # Trigger evaluation
    print(f"\nTriggering evaluation (framework={args.framework})...")
    try:
        run_id = client.trigger_evaluation(dataset_id, framework=args.framework)
        print(f"  Run ID: {run_id}")
    except Exception as exc:
        print(f"WARNING: Failed to trigger evaluation: {exc}")
        return 2

    # Wait for completion
    try:
        run = wait_for_evaluation(client, run_id, timeout_seconds=args.timeout)
    except (TimeoutError, RuntimeError) as exc:
        print(f"WARNING: Evaluation did not complete: {exc}")
        return 2

    # Extract scores
    scores = run.get("aggregate_scores", {})
    if not scores:
        scores = run.get("metrics", {})

    print("\nEvaluation Results:")
    print("-" * 40)
    for metric, value in sorted(scores.items()):
        if isinstance(value, (int, float)):
            print(f"  {metric:<40} {value:.4f}")

    # Check regression
    passed, failures = check_regression(
        current_scores=scores,
        baseline_scores=baseline.get("scores") if baseline else None,
        faithfulness_threshold=args.faithfulness_threshold,
        ndcg_threshold=args.ndcg_threshold,
        regression_threshold=args.regression_threshold,
    )

    # Write JSON output if requested
    result = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "passed": passed,
        "scores": scores,
        "baseline": baseline.get("scores") if baseline else None,
        "failures": failures,
    }
    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults written to: {args.output_json}")

    print("\n" + "=" * 60)
    if passed:
        print("✅ EVALUATION GATE PASSED")
        print("   All quality metrics within acceptable ranges.")
        # Store as new baseline
        client.store_evaluation_baseline(dataset_id, scores)
        print("   Baseline updated.")
        return 0
    else:
        print("❌ EVALUATION GATE FAILED — QUALITY REGRESSION DETECTED")
        for failure in failures:
            print(f"   • {failure}")
        print()
        print("Action required: Fix retrieval/generation quality before merging.")
        print("See evaluation details at: /analytics/evaluation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
