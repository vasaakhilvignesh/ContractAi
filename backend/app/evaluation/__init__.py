"""
ContractIQ — Retrieval Evaluation Package (Phase 5D)
"""

from app.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    calculate_retrieval_metrics,
    aggregate_metrics,
)
from app.evaluation.dataset import (
    EvalChunk,
    EvalContract,
    EvalQuery,
    RetrievalEvalDataset,
    load_default_eval_dataset,
)
from app.evaluation.evaluator import (
    MockEvalEmbeddingProvider,
    QueryEvaluationResult,
    RetrievalEvaluationReport,
    RetrievalEvaluator,
    make_unit_vector,
)

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank_at_k",
    "calculate_retrieval_metrics",
    "aggregate_metrics",
    "EvalChunk",
    "EvalContract",
    "EvalQuery",
    "RetrievalEvalDataset",
    "load_default_eval_dataset",
    "MockEvalEmbeddingProvider",
    "QueryEvaluationResult",
    "RetrievalEvaluationReport",
    "RetrievalEvaluator",
    "make_unit_vector",
]
