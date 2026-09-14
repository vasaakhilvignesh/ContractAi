"""
ContractIQ — Retrieval Evaluation Package (Phase 5D)
"""

from app.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    calculate_retrieval_metrics,
    aggregate_metrics,
    claim_groundedness_rate,
    citation_validity_rate,
    citation_completeness_rate,
    wrong_contract_citation_rate,
    hallucinated_chunk_rate,
    text_mismatch_rate,
    page_mismatch_rate,
    calculate_grounding_metrics,
)
from app.evaluation.dataset import (
    EvalChunk,
    EvalContract,
    EvalQuery,
    RetrievalEvalDataset,
    load_default_eval_dataset,
    GroundedEvalCitation,
    GroundedEvalClaim,
    GroundedEvalCase,
    GroundedEvaluationDataset,
    load_grounded_eval_dataset,
    get_default_grounded_eval_dataset,
)
from app.evaluation.evaluator import (
    MockEvalEmbeddingProvider,
    QueryEvaluationResult,
    RetrievalEvaluationReport,
    RetrievalEvaluator,
    make_unit_vector,
)
from app.evaluation.grounded_evaluator import (
    MockEvalStructuredLLMProvider,
    GroundedCaseEvaluationResult,
    GroundedEvaluationReport,
    GroundedRAGEvaluator,
)

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank_at_k",
    "calculate_retrieval_metrics",
    "aggregate_metrics",
    "claim_groundedness_rate",
    "citation_validity_rate",
    "citation_completeness_rate",
    "wrong_contract_citation_rate",
    "hallucinated_chunk_rate",
    "text_mismatch_rate",
    "page_mismatch_rate",
    "calculate_grounding_metrics",
    "EvalChunk",
    "EvalContract",
    "EvalQuery",
    "RetrievalEvalDataset",
    "load_default_eval_dataset",
    "GroundedEvalCitation",
    "GroundedEvalClaim",
    "GroundedEvalCase",
    "GroundedEvaluationDataset",
    "load_grounded_eval_dataset",
    "get_default_grounded_eval_dataset",
    "MockEvalEmbeddingProvider",
    "QueryEvaluationResult",
    "RetrievalEvaluationReport",
    "RetrievalEvaluator",
    "make_unit_vector",
    "MockEvalStructuredLLMProvider",
    "GroundedCaseEvaluationResult",
    "GroundedEvaluationReport",
    "GroundedRAGEvaluator",
]

