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

    keys = query_metrics[0].keys()
    aggregated = {}
    for key in keys:
        values = [qm.get(key, 0.0) for qm in query_metrics]
        aggregated[key] = round(sum(values) / float(len(values)), 6)

    return aggregated


# ====================================================================
# Grounded Generation & Citation Metrics (Phase 17B & 17C)
# ====================================================================

def claim_groundedness_rate(claims: list[Any]) -> float:
    """
    Computes Claim Groundedness Rate:
        CGR = (Number of Grounded Claims) / (Total Claims)
    A claim is grounded if it has at least one valid supporting citation.
    Returns 1.0 if total claims is 0 (vacuously true / no claims made).
    """
    if not claims:
        return 1.0

    grounded_count = 0
    for claim in claims:
        is_grounded = getattr(claim, "is_grounded", None)
        if is_grounded is None and isinstance(claim, dict):
            is_grounded = claim.get("is_grounded", False)
        if bool(is_grounded):
            grounded_count += 1

    return round(grounded_count / float(len(claims)), 6)


def citation_validity_rate(citations: list[Any]) -> float:
    """
    Computes Citation Validity Rate:
        CVR = (Number of Valid Citations) / (Total Citations)
    Returns 1.0 if total citations is 0.
    """
    if not citations:
        return 1.0

    valid_count = 0
    for cite in citations:
        status = getattr(cite, "verification_status", None)
        if status is None and isinstance(cite, dict):
            status = cite.get("verification_status")
        status_val = getattr(status, "value", str(status)) if status is not None else ""
        if status_val.lower() == "valid":
            valid_count += 1

    return round(valid_count / float(len(citations)), 6)


def citation_completeness_rate(claims: list[Any]) -> float:
    """
    Computes Citation Completeness Rate:
        CCR = (Number of Claims with >= 1 Citation) / (Total Claims)
    Returns 1.0 if total claims is 0.
    """
    if not claims:
        return 1.0

    cited_count = 0
    for claim in claims:
        citations = getattr(claim, "citations", None)
        if citations is None and isinstance(claim, dict):
            citations = claim.get("citations", [])
        if citations and len(citations) > 0:
            cited_count += 1

    return round(cited_count / float(len(claims)), 6)


def citation_error_rate(citations: list[Any], target_error: str) -> float:
    """
    Computes the occurrence rate of a specific citation error status
    (e.g., 'wrong_contract', 'chunk_not_found', 'text_mismatch', 'page_mismatch').
    """
    if not citations:
        return 0.0

    target = target_error.strip().lower()
    error_count = 0
    for cite in citations:
        status = getattr(cite, "verification_status", None)
        if status is None and isinstance(cite, dict):
            status = cite.get("verification_status")
        status_val = getattr(status, "value", str(status)) if status is not None else ""
        if status_val.lower() == target:
            error_count += 1

    return round(error_count / float(len(citations)), 6)


def wrong_contract_citation_rate(citations: list[Any]) -> float:
    """Computes fraction of citations referencing wrong contract."""
    return citation_error_rate(citations, "wrong_contract")


def hallucinated_chunk_rate(citations: list[Any]) -> float:
    """Computes fraction of citations referencing non-existent chunks."""
    return citation_error_rate(citations, "chunk_not_found")


def text_mismatch_rate(citations: list[Any]) -> float:
    """Computes fraction of citations with tampered/mismatched quote text."""
    return citation_error_rate(citations, "text_mismatch")


def page_mismatch_rate(citations: list[Any]) -> float:
    """Computes fraction of citations with incorrect page numbers."""
    return citation_error_rate(citations, "page_mismatch")


def calculate_grounding_metrics(claims: list[Any]) -> dict[str, float]:
    """
    Extracts all citations across claims and computes the full suite of
    grounding, citation quality, and hallucination detection metrics.
    """
    all_citations: list[Any] = []
    for claim in claims:
        cites = getattr(claim, "citations", None)
        if cites is None and isinstance(claim, dict):
            cites = claim.get("citations", [])
        if cites:
            all_citations.extend(cites)

    return {
        "claim_groundedness_rate": claim_groundedness_rate(claims),
        "citation_validity_rate": citation_validity_rate(all_citations),
        "citation_completeness_rate": citation_completeness_rate(claims),
        "wrong_contract_rate": wrong_contract_citation_rate(all_citations),
        "hallucinated_chunk_rate": hallucinated_chunk_rate(all_citations),
        "text_mismatch_rate": text_mismatch_rate(all_citations),
        "page_mismatch_rate": page_mismatch_rate(all_citations),
        "total_claims": float(len(claims)),
        "total_citations": float(len(all_citations)),
    }
