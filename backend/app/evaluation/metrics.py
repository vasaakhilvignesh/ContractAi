"""
ContractIQ — Information Retrieval Evaluation Metrics (Phase 5D)

Provides deterministic mathematical implementations of standard IR ranking metrics:
  - Precision@K: Fraction of top-K retrieved chunks that are relevant.
  - Recall@K: Fraction of total relevant chunks that appear in the top-K retrieved list.
  - MRR@K (Mean Reciprocal Rank): 1 / rank of the first relevant chunk in top-K (0 if none).
"""

import uuid
from typing import Any, Union

IdType = Union[str, uuid.UUID]


def _normalize_id(val: Any) -> str:
    """Normalize UUID or string ID to a clean lowercase string."""
    return str(val).strip().lower()


def precision_at_k(
    retrieved_ids: list[IdType],
    relevant_ids: set[IdType],
    k: int = 5,
) -> float:
    """
    Computes Precision@K:
        Precision@K = |Retrieved[:K] ∩ Relevant| / K

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs.
        relevant_ids: Set of ground-truth relevant chunk IDs.
        k: Cutoff rank (must be > 0).

    Returns:
        float: Precision at rank K in [0.0, 1.0], rounded to 6 decimal places.
    """
    if k <= 0 or not retrieved_ids or not relevant_ids:
        return 0.0

    normalized_relevant = {_normalize_id(rid) for rid in relevant_ids}
    top_k_retrieved = [_normalize_id(rid) for rid in retrieved_ids[:k]]

    relevant_retrieved_count = sum(
        1 for rid in top_k_retrieved if rid in normalized_relevant
    )

    return round(relevant_retrieved_count / float(k), 6)


def recall_at_k(
    retrieved_ids: list[IdType],
    relevant_ids: set[IdType],
    k: int = 5,
) -> float:
    """
    Computes Recall@K:
        Recall@K = |Retrieved[:K] ∩ Relevant| / |Relevant|

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs.
        relevant_ids: Set of ground-truth relevant chunk IDs.
        k: Cutoff rank (must be > 0).

    Returns:
        float: Recall at rank K in [0.0, 1.0], rounded to 6 decimal places.
    """
    if k <= 0 or not retrieved_ids or not relevant_ids:
        return 0.0

    normalized_relevant = {_normalize_id(rid) for rid in relevant_ids}
    if not normalized_relevant:
        return 0.0

    top_k_retrieved = [_normalize_id(rid) for rid in retrieved_ids[:k]]

    relevant_retrieved_count = sum(
        1 for rid in top_k_retrieved if rid in normalized_relevant
    )

    return round(relevant_retrieved_count / float(len(normalized_relevant)), 6)


def reciprocal_rank_at_k(
    retrieved_ids: list[IdType],
    relevant_ids: set[IdType],
    k: int = 5,
) -> float:
    """
    Computes Reciprocal Rank at K (RR@K) for a single query:
        RR@K = 1 / rank_of_first_relevant_item_in_top_k
        RR@K = 0.0 if no relevant items appear in top K.

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs.
        relevant_ids: Set of ground-truth relevant chunk IDs.
        k: Cutoff rank (must be > 0).

    Returns:
        float: Reciprocal rank in [0.0, 1.0], rounded to 6 decimal places.
    """
    if k <= 0 or not retrieved_ids or not relevant_ids:
        return 0.0

    normalized_relevant = {_normalize_id(rid) for rid in relevant_ids}
    top_k_retrieved = [_normalize_id(rid) for rid in retrieved_ids[:k]]

    for rank_idx, rid in enumerate(top_k_retrieved, start=1):
        if rid in normalized_relevant:
            return round(1.0 / rank_idx, 6)

    return 0.0


def calculate_retrieval_metrics(
    retrieved_ids: list[IdType],
    relevant_ids: set[IdType],
    k: int = 5,
) -> dict[str, float]:
    """
    Computes all standard retrieval evaluation metrics at cutoff K.

    Args:
        retrieved_ids: Ordered list of retrieved chunk IDs.
        relevant_ids: Set of ground-truth relevant chunk IDs.
        k: Cutoff rank.

    Returns:
        dict with precision@k, recall@k, and mrr@k.
    """
    return {
        f"precision@{k}": precision_at_k(retrieved_ids, relevant_ids, k=k),
        f"recall@{k}": recall_at_k(retrieved_ids, relevant_ids, k=k),
        f"mrr@{k}": reciprocal_rank_at_k(retrieved_ids, relevant_ids, k=k),
    }


def aggregate_metrics(
    query_metrics: list[dict[str, float]],
) -> dict[str, float]:
    """
    Computes the arithmetic mean for each metric across a list of query evaluation outputs.

    Args:
        query_metrics: List of metric dicts (one per query).

    Returns:
        dict[str, float]: Mean scores for each metric key, rounded to 6 decimal places.
    """
    if not query_metrics:
        return {}

    all_keys = list(query_metrics[0].keys())
    aggregated: dict[str, float] = {}

    for key in all_keys:
        values = [qm[key] for qm in query_metrics if key in qm]
        if values:
            aggregated[key] = round(sum(values) / len(values), 6)
        else:
            aggregated[key] = 0.0

    return aggregated
