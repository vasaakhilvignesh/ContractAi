"""
ContractIQ — Retrieval Evaluation Framework & Runner (Phase 5D)

Executes deterministic evaluation across all three retrieval methods:
  1. Semantic Vector Retrieval (Phase 5A)
  2. Keyword Full-Text Retrieval (Phase 5B)
  3. Hybrid Retrieval with RRF (Phase 5C)

Evaluates Precision@K, Recall@K, and MRR@K against ground-truth benchmarks
without making any live Gemini API calls, using fixed orthogonal unit vectors.
"""

import logging
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.dataset import EvalQuery, RetrievalEvalDataset, load_default_eval_dataset
from app.evaluation.metrics import calculate_retrieval_metrics, aggregate_metrics
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.services.embedding_provider import EmbeddingProvider, EmbeddingTaskType
from app.services.hybrid_retrieval_service import query_contract_hybrid
from app.services.keyword_retrieval_service import query_contract_keywords
from app.services.retrieval_service import query_contract_chunks

logger = logging.getLogger(__name__)


def make_unit_vector(dim: int = 768, active_index: int = 0) -> list[float]:
    """Returns a deterministic 768-dimensional unit vector with 1.0 at active_index."""
    vec = [0.0] * dim
    vec[active_index % dim] = 1.0
    return vec


class MockEvalEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic mock embedding provider for offline evaluation.
    Maps queries to fixed vectors based on registered query axes or query text lookup.
    """

    def __init__(self, query_axis_map: Optional[dict[str, int]] = None, default_axis: int = 0):
        self._query_axis_map = query_axis_map or {}
        self._default_axis = default_axis

    @property
    def model_name(self) -> str:
        return "mock-evaluation-embedder"

    @property
    def dimension(self) -> int:
        return 768

    async def embed_texts(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> list[list[float]]:
        return [make_unit_vector(self.dimension, self._default_axis) for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        axis = self._query_axis_map.get(query, self._default_axis)
        return make_unit_vector(self.dimension, axis)


class QueryEvaluationResult(BaseModel):
    """Evaluation result for a single query across all methods and K values."""

    query_id: str
    query: str
    query_type: str
    expected_chunk_ids: list[uuid.UUID]
    retrieved_chunk_ids: dict[str, list[uuid.UUID]] = Field(
        default_factory=dict,
        description="Method name -> ordered list of retrieved chunk UUIDs",
    )
    metrics_by_method: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Method name -> {metric@k: score}",
    )

    model_config = ConfigDict(from_attributes=True)


class RetrievalEvaluationReport(BaseModel):
    """Complete evaluation report with query-level and aggregated metrics."""

    dataset_name: str
    dataset_version: str
    total_queries: int
    k_values: list[int]
    method_summaries: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Method name -> aggregated metrics (mean precision@k, recall@k, mrr@k)",
    )
    query_results: list[QueryEvaluationResult] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    def format_summary_table(self) -> str:
        """Formats the aggregate metrics as a readable markdown table."""
        lines = [
            f"# Retrieval Evaluation Report: {self.dataset_name} (v{self.dataset_version})",
            f"**Total Queries:** {self.total_queries} | **Evaluated K Values:** {self.k_values}",
            "",
            "| Retrieval Method | " + " | ".join(
                [f"P@{k} | R@{k} | MRR@{k}" for k in self.k_values]
            ) + " |",
            "| :--- | " + " | ".join(["---: | ---: | ---:" for _ in self.k_values]) + " |",
        ]

        for method, metrics in self.method_summaries.items():
            row_parts = [f"**{method.capitalize()}**"]
            for k in self.k_values:
                p = metrics.get(f"precision@{k}", 0.0)
                r = metrics.get(f"recall@{k}", 0.0)
                mrr = metrics.get(f"mrr@{k}", 0.0)
                row_parts.append(f"{p:.4f} | {r:.4f} | {mrr:.4f}")
            lines.append("| " + " | ".join(row_parts) + " |")

        return "\n".join(lines)


class RetrievalEvaluator:
    """
    Orchestrates the execution and scoring of retrieval evaluation suites.
    """

    def __init__(self, dataset: Optional[RetrievalEvalDataset] = None):
        self.dataset = dataset or load_default_eval_dataset()

    def build_mock_provider(self) -> MockEvalEmbeddingProvider:
        """Builds a deterministic mock provider mapped to the dataset's query vectors."""
        axis_map = {q.query: q.vector_axis for q in self.dataset.queries}
        return MockEvalEmbeddingProvider(query_axis_map=axis_map)

    def seed_dataset(self, db: Session) -> Contract:
        """
        Seeds the evaluation contract and chunks into the active PostgreSQL session.
        If contract already exists, cleans it up first to ensure clean state.
        """
        c_meta = self.dataset.contract

        # Clean existing test records if present
        self.cleanup_dataset(db)

        # Create contract
        contract = Contract(
            id=c_meta.id,
            title=c_meta.title,
            vendor=c_meta.vendor,
            contract_type=c_meta.contract_type,
            status=c_meta.status,
            processing_status="completed",
            page_count=max((ch.page_number for ch in c_meta.chunks), default=1),
        )
        db.add(contract)
        db.commit()

        # Insert chunks with fixed unit vectors
        db_chunks = []
        for ch in c_meta.chunks:
            chunk = DocumentChunk(
                id=ch.id,
                contract_id=contract.id,
                chunk_index=ch.chunk_index,
                page_number=ch.page_number,
                section_header=ch.section_header,
                text=ch.text,
                char_start=ch.char_start,
                char_end=ch.char_end,
                embedding=make_unit_vector(768, ch.vector_axis),
            )
            db_chunks.append(chunk)

        db.add_all(db_chunks)
        db.commit()
        return contract

    def cleanup_dataset(self, db: Session) -> None:
        """Removes the evaluation contract and chunks from PostgreSQL."""
        c_id = self.dataset.contract.id
        db.query(DocumentChunk).filter(DocumentChunk.contract_id == c_id).delete(synchronize_session=False)
        db.query(Contract).filter(Contract.id == c_id).delete(synchronize_session=False)
        db.commit()

    async def evaluate(
        self,
        db: Session,
        k_values: list[int] = [1, 3, 5],
        methods: list[str] = ["semantic", "keyword", "hybrid"],
    ) -> RetrievalEvaluationReport:
        """
        Executes evaluation across all configured methods and queries.

        Args:
            db: Active database session with seeded benchmark data.
            k_values: List of rank cutoffs to evaluate (e.g. [1, 3, 5]).
            methods: Retrieval methods to benchmark ("semantic", "keyword", "hybrid").

        Returns:
            RetrievalEvaluationReport containing query results and aggregated metrics.
        """
        contract_id = self.dataset.contract.id
        provider = self.build_mock_provider()
        max_k = max(k_values, default=5)

        query_results: list[QueryEvaluationResult] = []
        method_query_metrics: dict[str, list[dict[str, float]]] = {m: [] for m in methods}

        for q in self.dataset.queries:
            q_result = QueryEvaluationResult(
                query_id=q.query_id,
                query=q.query,
                query_type=q.query_type,
                expected_chunk_ids=q.expected_chunk_ids,
            )

            expected_set = set(q.expected_chunk_ids)

            # 1. Evaluate Semantic Retrieval
            if "semantic" in methods:
                sem_resp = await query_contract_chunks(
                    db=db,
                    contract_id=contract_id,
                    query=q.query,
                    top_k=max_k,
                    provider=provider,
                )
                sem_ids = [m.id for m in sem_resp.matches]
                q_result.retrieved_chunk_ids["semantic"] = sem_ids

                sem_metrics: dict[str, float] = {}
                for k in k_values:
                    sem_metrics.update(calculate_retrieval_metrics(sem_ids, expected_set, k=k))
                q_result.metrics_by_method["semantic"] = sem_metrics
                method_query_metrics["semantic"].append(sem_metrics)

            # 2. Evaluate Keyword Retrieval
            if "keyword" in methods:
                kw_resp = await query_contract_keywords(
                    db=db,
                    contract_id=contract_id,
                    query=q.query,
                    top_k=max_k,
                )
                kw_ids = [m.id for m in kw_resp.matches]
                q_result.retrieved_chunk_ids["keyword"] = kw_ids

                kw_metrics: dict[str, float] = {}
                for k in k_values:
                    kw_metrics.update(calculate_retrieval_metrics(kw_ids, expected_set, k=k))
                q_result.metrics_by_method["keyword"] = kw_metrics
                method_query_metrics["keyword"].append(kw_metrics)

            # 3. Evaluate Hybrid Retrieval (RRF)
            if "hybrid" in methods:
                hyb_resp = await query_contract_hybrid(
                    db=db,
                    contract_id=contract_id,
                    query=q.query,
                    top_k=max_k,
                    provider=provider,
                )
                hyb_ids = [m.id for m in hyb_resp.matches]
                q_result.retrieved_chunk_ids["hybrid"] = hyb_ids

                hyb_metrics: dict[str, float] = {}
                for k in k_values:
                    hyb_metrics.update(calculate_retrieval_metrics(hyb_ids, expected_set, k=k))
                q_result.metrics_by_method["hybrid"] = hyb_metrics
                method_query_metrics["hybrid"].append(hyb_metrics)

            query_results.append(q_result)

        # Compute aggregate metrics per method
        summaries: dict[str, dict[str, float]] = {}
        for m in methods:
            summaries[m] = aggregate_metrics(method_query_metrics[m])

        return RetrievalEvaluationReport(
            dataset_name=self.dataset.name,
            dataset_version=self.dataset.version,
            total_queries=len(self.dataset.queries),
            k_values=k_values,
            method_summaries=summaries,
            query_results=query_results,
        )
