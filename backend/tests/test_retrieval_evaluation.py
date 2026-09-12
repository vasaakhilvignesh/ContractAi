"""
ContractIQ — Tests for Information Retrieval Evaluation Framework (Phase 5D)

Verifies:
  1. Precision@K calculation accuracy across diverse retrieval scenarios.
  2. Recall@K calculation accuracy across diverse retrieval scenarios.
  3. MRR@K (Reciprocal Rank) calculation accuracy across diverse rank positions.
  4. Metric edge cases (empty sets, k <= 0, truncated result lists).
  5. Aggregated metric computations across multi-query evaluation runs.
  6. Evaluation dataset loader and schema validation (JSON benchmark fixtures).
  7. Deterministic evaluation runner across all 3 methods (semantic, keyword, hybrid).
  8. Zero live Gemini API calls during evaluation (using fixed orthogonal vectors).
  9. Comprehensive reporting with formatted audit-ready markdown summary table.
"""

import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.evaluation.dataset import (
    EvalChunk,
    EvalContract,
    EvalQuery,
    RetrievalEvalDataset,
    load_default_eval_dataset,
)
from app.evaluation.evaluator import (
    MockEvalEmbeddingProvider,
    RetrievalEvaluationReport,
    RetrievalEvaluator,
    make_unit_vector,
)
from app.evaluation.metrics import (
    aggregate_metrics,
    calculate_retrieval_metrics,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
)


# ====================================================================
# Unit Tests: Metric Calculations
# ====================================================================

class TestRetrievalMetrics:
    """Unit tests validating IR evaluation metric formulas and boundary cases."""

    def test_precision_at_k(self):
        """Precision@K = |Retrieved[:K] ∩ Relevant| / K."""
        rel = {"c1", "c2"}

        # 2 of top 2 relevant -> 2 / 2 = 1.0
        assert precision_at_k(["c1", "c2", "c3"], rel, k=2) == 1.0

        # 1 of top 2 relevant -> 1 / 2 = 0.5
        assert precision_at_k(["c1", "c3", "c2"], rel, k=2) == 0.5

        # 2 of top 5 relevant -> 2 / 5 = 0.4
        assert precision_at_k(["c1", "c2", "c3", "c4", "c5"], rel, k=5) == 0.4

        # 0 of top 3 relevant -> 0 / 3 = 0.0
        assert precision_at_k(["c3", "c4", "c5"], rel, k=3) == 0.0

    def test_recall_at_k(self):
        """Recall@K = |Retrieved[:K] ∩ Relevant| / |Relevant|."""
        rel = {"c1", "c2"}

        # Both relevant retrieved in top 3 -> 2 / 2 = 1.0
        assert recall_at_k(["c1", "c3", "c2"], rel, k=3) == 1.0

        # 1 of 2 relevant retrieved in top 2 -> 1 / 2 = 0.5
        assert recall_at_k(["c1", "c3", "c2"], rel, k=2) == 0.5

        # 0 of 2 relevant retrieved -> 0 / 2 = 0.0
        assert recall_at_k(["c3", "c4"], rel, k=2) == 0.0

    def test_reciprocal_rank_at_k(self):
        """RR@K = 1 / rank of first relevant item in top K, or 0.0 if not in top K."""
        rel = {"target"}

        # First item is relevant (rank 1) -> 1.0
        assert reciprocal_rank_at_k(["target", "c2", "c3"], rel, k=3) == 1.0

        # Second item is relevant (rank 2) -> 1/2 = 0.5
        assert reciprocal_rank_at_k(["c1", "target", "c3"], rel, k=3) == 0.5

        # Third item is relevant (rank 3) -> 1/3 ~ 0.333333
        assert reciprocal_rank_at_k(["c1", "c2", "target"], rel, k=3) == round(1.0 / 3, 6)

        # Relevant item at rank 4, but k=3 -> 0.0
        assert reciprocal_rank_at_k(["c1", "c2", "c3", "target"], rel, k=3) == 0.0

    def test_metric_edge_cases(self):
        """Validates robust behavior on empty sets, invalid k, and UUID objects."""
        u1 = uuid.uuid4()
        u2 = uuid.uuid4()

        # Works with UUID objects seamlessly
        assert precision_at_k([u1, u2], {u1}, k=2) == 0.5
        assert recall_at_k([u1, u2], {u1}, k=2) == 1.0
        assert reciprocal_rank_at_k([u1, u2], {u1}, k=2) == 1.0

        # Empty retrieved list
        assert precision_at_k([], {u1}, k=5) == 0.0
        assert recall_at_k([], {u1}, k=5) == 0.0
        assert reciprocal_rank_at_k([], {u1}, k=5) == 0.0

        # Empty relevant set
        assert precision_at_k([u1], set(), k=5) == 0.0
        assert recall_at_k([u1], set(), k=5) == 0.0
        assert reciprocal_rank_at_k([u1], set(), k=5) == 0.0

        # k <= 0
        assert precision_at_k([u1], {u1}, k=0) == 0.0
        assert recall_at_k([u1], {u1}, k=-1) == 0.0
        assert reciprocal_rank_at_k([u1], {u1}, k=0) == 0.0

    def test_calculate_retrieval_metrics(self):
        """calculate_retrieval_metrics bundles precision, recall, and mrr at K."""
        metrics = calculate_retrieval_metrics(["c1", "c2", "c3"], {"c1"}, k=3)
        assert metrics["precision@3"] == round(1.0 / 3, 6)
        assert metrics["recall@3"] == 1.0
        assert metrics["mrr@3"] == 1.0

    def test_aggregate_metrics(self):
        """aggregate_metrics averages across multiple query outputs."""
        q1 = {"precision@1": 1.0, "mrr@1": 1.0}
        q2 = {"precision@1": 0.0, "mrr@1": 0.0}
        agg = aggregate_metrics([q1, q2])
        assert agg["precision@1"] == 0.5
        assert agg["mrr@1"] == 0.5


# ====================================================================
# Unit Tests: Evaluation Dataset
# ====================================================================

class TestRetrievalDataset:
    """Validates the structure and content of the benchmark dataset."""

    def test_load_default_eval_dataset(self):
        """Loads and verifies default benchmark dataset from JSON."""
        dataset = load_default_eval_dataset()

        assert dataset.name == "ContractIQ Standard Retrieval Benchmark"
        assert dataset.version == "1.0"
        assert len(dataset.contract.chunks) == 5
        assert len(dataset.queries) == 5

        # Check all query expected_chunk_ids are present in contract chunks
        contract_chunk_ids = {ch.id for ch in dataset.contract.chunks}
        for q in dataset.queries:
            for expected_id in q.expected_chunk_ids:
                assert expected_id in contract_chunk_ids, f"Query {q.query_id} expects unknown chunk {expected_id}"

    def test_dataset_models_validation(self):
        """Verifies Pydantic model validation on dataset objects."""
        chunk = EvalChunk(
            id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            text="Test chunk text",
            vector_axis=5,
        )
        assert chunk.vector_axis == 5

        query = EvalQuery(
            query_id="q-test",
            query="test query",
            query_type="semantic",
            vector_axis=5,
            expected_chunk_ids=[chunk.id],
        )
        assert len(query.expected_chunk_ids) == 1


# ====================================================================
# Integration Tests: Evaluation Runner & Reporting
# ====================================================================

@pytest.fixture
def db_session():
    """Provides a database session for evaluation tests."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


class TestRetrievalEvaluator:
    """Integration tests running evaluation across semantic, keyword, and hybrid methods."""

    @pytest.mark.asyncio
    async def test_evaluator_end_to_end(self, db_session: Session):
        """
        Executes end-to-end evaluation for all three retrieval methods against PostgreSQL.
        Verifies:
          - Contract and chunks seeded with fixed unit vectors.
          - Evaluation runs deterministically for semantic, keyword, and hybrid.
          - Aggregated Precision@K, Recall@K, and MRR@K are reported.
          - Summary markdown table formats cleanly.
          - Database cleanup is executed.
        """
        dataset = load_default_eval_dataset()
        evaluator = RetrievalEvaluator(dataset=dataset)

        try:
            # Seed dataset
            evaluator.seed_dataset(db_session)

            # Run evaluation across all 3 methods at cutoffs [1, 3, 5]
            report: RetrievalEvaluationReport = await evaluator.evaluate(
                db=db_session,
                k_values=[1, 3, 5],
                methods=["semantic", "keyword", "hybrid"],
            )

            # Verify report structure
            assert report.total_queries == len(dataset.queries)
            assert report.k_values == [1, 3, 5]
            assert "semantic" in report.method_summaries
            assert "keyword" in report.method_summaries
            assert "hybrid" in report.method_summaries

            # Check individual method metrics exist and are non-negative
            for method in ["semantic", "keyword", "hybrid"]:
                summary = report.method_summaries[method]
                for k in [1, 3, 5]:
                    assert f"precision@{k}" in summary
                    assert f"recall@{k}" in summary
                    assert f"mrr@{k}" in summary
                    assert 0.0 <= summary[f"precision@{k}"] <= 1.0
                    assert 0.0 <= summary[f"recall@{k}"] <= 1.0
                    assert 0.0 <= summary[f"mrr@{k}"] <= 1.0

            # Semantic and Hybrid should achieve strong MRR with our aligned vectors
            assert report.method_summaries["semantic"]["mrr@5"] >= 0.8
            assert report.method_summaries["hybrid"]["mrr@5"] >= 0.8

            # Verify markdown table generation
            table = report.format_summary_table()
            assert "# Retrieval Evaluation Report" in table
            assert "Semantic" in table
            assert "Keyword" in table
            assert "Hybrid" in table
            print("\n" + table)

        finally:
            evaluator.cleanup_dataset(db_session)

    @pytest.mark.asyncio
    async def test_deterministic_without_gemini_api(self):
        """Verifies MockEvalEmbeddingProvider returns deterministic vectors without network calls."""
        provider = MockEvalEmbeddingProvider(
            query_axis_map={"test query": 42},
            default_axis=0,
        )

        vec_mapped = await provider.embed_query("test query")
        assert len(vec_mapped) == 768
        assert vec_mapped[42] == 1.0
        assert sum(vec_mapped) == 1.0

        vec_default = await provider.embed_query("unmapped query")
        assert vec_default[0] == 1.0
        assert sum(vec_default) == 1.0
