import math
from collections.abc import Sequence


def mean_reciprocal_rank(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str]) -> float:
    """Computes Reciprocal Rank for the first relevant chunk in retrieved_ids."""
    gt_set = set(ground_truth_ids)
    if not gt_set or not retrieved_ids:
        return 0.0

    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in gt_set:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str], k: int = 5) -> float:
    """Precision@K: (number of relevant items in top K) / K."""
    if k <= 0 or not retrieved_ids:
        return 0.0
    gt_set = set(ground_truth_ids)
    top_k = retrieved_ids[:k]
    hits = sum(1 for item in top_k if item in gt_set)
    return hits / min(k, len(top_k))


def recall_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str], k: int = 5) -> float:
    """Recall@K: (number of relevant items in top K) / (total ground truth items)."""
    gt_set = set(ground_truth_ids)
    if not gt_set or k <= 0 or not retrieved_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for item in top_k if item in gt_set)
    return hits / len(gt_set)


def hit_rate_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str], k: int = 5) -> float:
    """HitRate@K: 1.0 if at least one relevant document appears in top K, else 0.0."""
    gt_set = set(ground_truth_ids)
    top_k = retrieved_ids[:k]
    for item in top_k:
        if item in gt_set:
            return 1.0
    return 0.0


def ndcg_at_k(retrieved_ids: Sequence[str], ground_truth_ids: Sequence[str], k: int = 5) -> float:
    """Normalized Discounted Cumulative Gain at rank K with binary relevance."""
    gt_set = set(ground_truth_ids)
    if not gt_set or not retrieved_ids or k <= 0:
        return 0.0

    # DCG@K
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        rel = 1.0 if doc_id in gt_set else 0.0
        dcg += rel / math.log2(i + 2)

    # IDCG@K (Ideal DCG where all relevant items appear first)
    idcg = 0.0
    ideal_hits = min(len(gt_set), k)
    for i in range(ideal_hits):
        idcg += 1.0 / math.log2(i + 2)

    if idcg == 0.0:
        return 0.0
    return round(dcg / idcg, 4)
