from collections.abc import Sequence

import structlog

logger = structlog.get_logger(__name__)


def calculate_context_precision(
    retrieved_chunk_ids: Sequence[str], ground_truth_chunk_ids: Sequence[str], k: int = 5
) -> float:
    """Context Precision evaluates whether ground-truth relevant chunks appear at the highest ranks.

    Formula: sum(precision@k * v_k) / total_relevant_in_top_k
    where v_k is 1 if chunk at rank k is relevant, 0 otherwise.
    """
    gt_set = set(ground_truth_chunk_ids)
    if not gt_set or not retrieved_chunk_ids:
        return 0.0

    top_k = retrieved_chunk_ids[:k]
    precisions = []
    hits = 0

    for i, cid in enumerate(top_k, start=1):
        if cid in gt_set:
            hits += 1
            precisions.append(hits / i)

    if not precisions:
        return 0.0

    return round(sum(precisions) / len(precisions), 4)


def calculate_context_recall(retrieved_chunk_ids: Sequence[str], ground_truth_chunk_ids: Sequence[str]) -> float:
    """Context Recall evaluates the proportion of ground-truth chunks retrieved in candidates."""
    gt_set = set(ground_truth_chunk_ids)
    if not gt_set or not retrieved_chunk_ids:
        return 0.0

    ret_set = set(retrieved_chunk_ids)
    hits = len(gt_set.intersection(ret_set))
    return round(hits / len(gt_set), 4)


def calculate_faithfulness(claims: Sequence[str], verified_claims_count: int) -> float:
    """Faithfulness = number of entailed claims / total claims made in generated answer."""
    if not claims:
        return 1.0
    return round(verified_claims_count / len(claims), 4)


def calculate_answer_relevancy_heuristic(query: str, generated_answer: str) -> float:
    """Computes keyword / overlap relevancy between question and answer as a baseline heuristic."""
    q_words = set(query.lower().split())
    a_words = set(generated_answer.lower().split())

    # Ignore trivial stopwords
    stopwords = {"what", "is", "the", "a", "an", "and", "in", "of", "to", "for", "how", "why", "are"}
    q_sig = q_words - stopwords
    if not q_sig:
        return 1.0

    overlap = len(q_sig.intersection(a_words))
    score = min(1.0, overlap / len(q_sig) + 0.3)
    return round(score, 4)
