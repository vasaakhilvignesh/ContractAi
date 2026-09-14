"""
ContractIQ — RAG Evaluation & Quality Regression Suite (Phase 17A–17E)

Verifies:
  17A: Retrieval Regression Evaluation (Precision@K, Recall@K, MRR@K across semantic, keyword, hybrid).
  17B: Grounded Generation Evaluation (supported claims, citation validity, completeness, cross-contract QA).
  17C: Hallucination & Unsupported-Claim Detection (wrong contract, text mismatch, page mismatch, missing chunks).
  17D: Comprehensive 13 Failure-Modes Regression Suite (all 13 edge cases and failure modes).
  17E: Quality Reporting & Critical Invariant Thresholds (JSON report, Markdown summary, 0% invariant tolerance).
"""

import json
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.evaluation.dataset import (
    EvalChunk,
    EvalContract,
    EvalQuery,
    GroundedEvalCase,
    GroundedEvalCitation,
    GroundedEvalClaim,
    GroundedEvaluationDataset,
    RetrievalEvalDataset,
    get_default_grounded_eval_dataset,
    load_default_eval_dataset,
    load_grounded_eval_dataset,
)
from app.evaluation.evaluator import (
    MockEvalEmbeddingProvider,
    RetrievalEvaluationReport,
    RetrievalEvaluator,
    make_unit_vector,
)
from app.evaluation.grounded_evaluator import (
    GroundedCaseEvaluationResult,
    GroundedEvaluationReport,
    GroundedRAGEvaluator,
    MockEvalStructuredLLMProvider,
)
from app.evaluation.metrics import (
    aggregate_metrics,
    calculate_grounding_metrics,
    calculate_retrieval_metrics,
    citation_completeness_rate,
    citation_error_rate,
    citation_validity_rate,
    claim_groundedness_rate,
    hallucinated_chunk_rate,
    page_mismatch_rate,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    text_mismatch_rate,
    wrong_contract_citation_rate,
)
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.rag import (
    AnswerClaim,
    CitationVerificationStatus,
    LLMCitationItem,
    LLMClaimItem,
    RAGCitation,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGStatus,
    StructuredRAGAnswerLLM,
)
from app.services.analyst_service import (
    ask_contract_analyst_cross,
    ask_contract_analyst_single,
)
from app.services.rag_service import (
    ContractNotFoundError,
    RAGServiceError,
    answer_contract_query_grounded,
    build_grounded_context,
    verify_citation,
)
from app.services.structured_output_provider import (
    StructuredOutputValidationError,
)


# ====================================================================
# Pytest Fixtures
# ====================================================================

@pytest.fixture
def db_session():
    """Provides an isolated database session for testing."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


# ====================================================================
# Phase 17A: Retrieval Regression Evaluation Tests
# ====================================================================

class TestRetrievalRegression:
    """Tests evaluating retrieval metrics and regression dataset fidelity."""

    def test_ir_metrics_precision_recall_mrr(self):
        """Validates Precision@K, Recall@K, and MRR@K formulas."""
        retrieved = ["chunk-1", "chunk-2", "chunk-3", "chunk-4", "chunk-5"]
        relevant = {"chunk-2", "chunk-4"}

        p5 = precision_at_k(retrieved, relevant, k=5)
        r5 = recall_at_k(retrieved, relevant, k=5)
        mrr5 = reciprocal_rank_at_k(retrieved, relevant, k=5)

        assert p5 == 0.4  # 2 of 5 retrieved are relevant
        assert r5 == 1.0  # both relevant retrieved in top 5
        assert mrr5 == 0.5  # first relevant appeared at rank 2 (1/2)

    def test_metrics_empty_and_boundary_handling(self):
        """Ensures robust 0.0 scores on empty lists, missing elements, and invalid K."""
        assert precision_at_k([], {"c1"}, k=5) == 0.0
        assert recall_at_k(["c1"], set(), k=5) == 0.0
        assert reciprocal_rank_at_k(["c2"], {"c1"}, k=5) == 0.0
        assert precision_at_k(["c1"], {"c1"}, k=0) == 0.0

    def test_dataset_loader_and_schema_validation(self):
        """Verifies loading of the retrieval evaluation dataset from JSON."""
        ds = load_default_eval_dataset()
        assert ds.name == "ContractIQ Standard Retrieval Benchmark"
        assert len(ds.contract.chunks) == 5
        assert len(ds.queries) == 5

        # Check all query axes and chunks are valid
        for q in ds.queries:
            assert q.vector_axis >= 0
            assert len(q.expected_chunk_ids) > 0


# ====================================================================
# Phase 17B: Grounded Generation Evaluation Tests
# ====================================================================

class TestGroundedGenerationEvaluation:
    """Tests evaluating grounded answer quality, citation completeness, and claims."""

    def test_grounding_metrics_calculation(self):
        """Validates calculation of groundedness rate and citation validity rate."""
        claims = [
            {
                "claim_text": "Party may terminate with 60 days notice.",
                "is_grounded": True,
                "citations": [
                    {"verification_status": CitationVerificationStatus.VALID}
                ],
            },
            {
                "claim_text": "Liability is capped at 12 months fees.",
                "is_grounded": True,
                "citations": [
                    {"verification_status": CitationVerificationStatus.VALID}
                ],
            },
            {
                "claim_text": "Governing law is Delaware.",
                "is_grounded": False,
                "citations": [
                    {"verification_status": CitationVerificationStatus.PAGE_MISMATCH}
                ],
            },
        ]

        metrics = calculate_grounding_metrics(claims)
        assert metrics["total_claims"] == 3.0
        assert metrics["total_citations"] == 3.0
        assert metrics["claim_groundedness_rate"] == round(2.0 / 3.0, 6)
        assert metrics["citation_validity_rate"] == round(2.0 / 3.0, 6)
        assert metrics["citation_completeness_rate"] == 1.0
        assert metrics["page_mismatch_rate"] == round(1.0 / 3.0, 6)
        assert metrics["wrong_contract_rate"] == 0.0

    def test_claim_without_citations_marked_unsupported(self):
        """Verifies that claims with empty citations are flagged as not grounded."""
        claim_without_cite = {
            "claim_text": "Vendor guarantees 99.99% uptime SLA.",
            "is_grounded": False,
            "citations": [],
        }
        assert claim_groundedness_rate([claim_without_cite]) == 0.0
        assert citation_completeness_rate([claim_without_cite]) == 0.0


# ====================================================================
# Phase 17C: Hallucination & Unsupported-Claim Detection Tests
# ====================================================================

class TestHallucinationDetection:
    """Tests deterministic detection and rejection of hallucinated citations and claims."""

    def test_detect_wrong_contract_citation(self, db_session: Session):
        """Verifies citation referencing a chunk from another contract is flagged WRONG_CONTRACT."""
        c1 = Contract(id=uuid.uuid4(), title="Contract Alpha", status="active")
        c2 = Contract(id=uuid.uuid4(), title="Contract Beta", status="active")
        db_session.add_all([c1, c2])
        db_session.commit()

        chunk_beta = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=c2.id,
            chunk_index=0,
            page_number=1,
            text="Beta terms are strictly confidential.",
        )
        db_session.add(chunk_beta)
        db_session.commit()

        try:
            # Alpha queries, but citation references Beta's chunk
            _, _, _, status, note = verify_citation(
                db=db_session,
                contract_id=c1.id,
                chunk_id_str=str(chunk_beta.id),
                verbatim_quote="Beta terms are strictly confidential.",
                page_number=1,
            )
            assert status == CitationVerificationStatus.WRONG_CONTRACT
            assert "not queried contract" in note
        finally:
            db_session.query(DocumentChunk).filter(DocumentChunk.id == chunk_beta.id).delete()
            db_session.query(Contract).filter(Contract.id.in_([c1.id, c2.id])).delete()
            db_session.commit()

    def test_detect_text_mismatch_tampered_quote(self, db_session: Session):
        """Verifies citation with altered/fabricated quote text is flagged TEXT_MISMATCH."""
        c = Contract(id=uuid.uuid4(), title="Test Contract", status="active")
        db_session.add(c)
        db_session.commit()

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=c.id,
            chunk_index=0,
            page_number=1,
            text="Termination for convenience requires sixty (60) days prior notice.",
        )
        db_session.add(chunk)
        db_session.commit()

        try:
            # LLM quotes "ninety (90) days" instead of sixty
            _, _, _, status, note = verify_citation(
                db=db_session,
                contract_id=c.id,
                chunk_id_str=str(chunk.id),
                verbatim_quote="requires ninety (90) days prior notice.",
                page_number=1,
            )
            assert status == CitationVerificationStatus.TEXT_MISMATCH
            assert "Verbatim quote was not found" in note
        finally:
            db_session.query(DocumentChunk).filter(DocumentChunk.id == chunk.id).delete()
            db_session.query(Contract).filter(Contract.id == c.id).delete()
            db_session.commit()

    def test_detect_non_existent_chunk(self, db_session: Session):
        """Verifies citation referencing a non-existent chunk ID is flagged CHUNK_NOT_FOUND."""
        c = Contract(id=uuid.uuid4(), title="Test Contract", status="active")
        db_session.add(c)
        db_session.commit()

        try:
            fake_chunk_id = str(uuid.uuid4())
            _, _, _, status, note = verify_citation(
                db=db_session,
                contract_id=c.id,
                chunk_id_str=fake_chunk_id,
                verbatim_quote="Some contractual quote",
                page_number=1,
            )
            assert status == CitationVerificationStatus.CHUNK_NOT_FOUND
            assert "does not exist" in note
        finally:
            db_session.query(Contract).filter(Contract.id == c.id).delete()
            db_session.commit()

    def test_detect_page_number_mismatch(self, db_session: Session):
        """Verifies citation stating page 9 when chunk is on page 1 is flagged PAGE_MISMATCH."""
        c = Contract(id=uuid.uuid4(), title="Test Contract", status="active")
        db_session.add(c)
        db_session.commit()

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=c.id,
            chunk_index=0,
            page_number=1,
            text="Governing law is State of Delaware.",
        )
        db_session.add(chunk)
        db_session.commit()

        try:
            _, resolved_page, _, status, note = verify_citation(
                db=db_session,
                contract_id=c.id,
                chunk_id_str=str(chunk.id),
                verbatim_quote="State of Delaware",
                page_number=9,  # Incorrect page
            )
            assert status == CitationVerificationStatus.PAGE_MISMATCH
            assert "Citation stated page 9" in note
        finally:
            db_session.query(DocumentChunk).filter(DocumentChunk.id == chunk.id).delete()
            db_session.query(Contract).filter(Contract.id == c.id).delete()
            db_session.commit()


# ====================================================================
# Phase 17D: RAG Failure-Case Regression Suite (13 Failure Modes)
# ====================================================================

class TestRAGFailureCasesRegressionSuite:
    """
    Dedicated regression test cases covering all 13 critical RAG failure modes.
    """

    @pytest.fixture(autouse=True)
    def setup_evaluation_contracts(self, db_session: Session):
        """Seeds standard benchmark contracts into DB and cleans them up after each test."""
        evaluator = GroundedRAGEvaluator()
        evaluator.seed_dataset(db_session)
        yield evaluator
        evaluator.cleanup_dataset(db_session)

    @pytest.mark.asyncio
    async def test_failure_mode_1_no_retrieval_matches(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 1: Query matches zero chunks -> NO_RETRIEVAL_MATCHES without LLM call."""
        c3_id = uuid.UUID("33333333-3333-4333-8333-333333333333")
        req = RAGQueryRequest(
            query="xyznonexistentcryptoxyz cryogenic storage",
            top_k=5,
        )
        provider = MockEvalEmbeddingProvider(default_axis=700)
        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c3_id,
            request=req,
            embedding_provider=provider,
        )
        assert resp.status == RAGStatus.NO_RETRIEVAL_MATCHES
        assert resp.has_sufficient_evidence is False
        assert resp.claims == []

    @pytest.mark.asyncio
    async def test_failure_mode_2_insufficient_evidence_in_context(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 2: Context lacks facts to answer query -> INSUFFICIENT_EVIDENCE."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        req = RAGQueryRequest(query="What is the early payment discount rate?", top_k=5)

        provider = MockEvalEmbeddingProvider(default_axis=0)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="The contract excerpts do not contain payment discount information.",
                    has_sufficient_evidence=False,
                    claims=[],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert resp.status == RAGStatus.INSUFFICIENT_EVIDENCE
        assert resp.has_sufficient_evidence is False
        assert resp.claims == []

    @pytest.mark.asyncio
    async def test_failure_mode_3_low_retrieval_confidence(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 3: Top match score below threshold -> LOW_RETRIEVAL_CONFIDENCE."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        req = RAGQueryRequest(
            query="quantum encryption protocols",
            min_score_threshold=0.999,  # Impossibly high threshold
        )
        provider = MockEvalEmbeddingProvider(default_axis=0)

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
        )
        assert resp.status == RAGStatus.LOW_RETRIEVAL_CONFIDENCE
        assert resp.has_sufficient_evidence is False

    @pytest.mark.asyncio
    async def test_failure_mode_4_non_existent_chunk_id(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 4: Citation references non-existent chunk UUID -> CHUNK_NOT_FOUND."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        req = RAGQueryRequest(query="What is the notice period for convenience?")
        fake_id = "99999999-9999-9999-9999-999999999999"

        provider = MockEvalEmbeddingProvider(default_axis=0)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="Notice period is 60 days.",
                    has_sufficient_evidence=True,
                    claims=[
                        LLMClaimItem(
                            claim="Either party may terminate upon 60 days notice.",
                            citations=[
                                LLMCitationItem(
                                    chunk_id=fake_id,
                                    page_number=1,
                                    verbatim_quote="upon sixty (60) days prior written notice",
                                )
                            ],
                        )
                    ],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert resp.status == RAGStatus.ANSWERED
        assert len(resp.claims) == 1
        claim = resp.claims[0]
        # Invariant: Claim must NOT be accepted as grounded
        assert claim.is_grounded is False
        assert claim.citations[0].verification_status == CitationVerificationStatus.CHUNK_NOT_FOUND

    @pytest.mark.asyncio
    async def test_failure_mode_5_citation_to_wrong_contract(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 5: Citation references chunk belonging to different contract -> WRONG_CONTRACT."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        ch6_id = "bbbb0001-0001-4001-8001-000000000001"  # Belongs to c2
        req = RAGQueryRequest(query="What is the initial term length?")

        provider = MockEvalEmbeddingProvider(default_axis=0)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="Initial term length is two years.",
                    has_sufficient_evidence=True,
                    claims=[
                        LLMClaimItem(
                            claim="The agreement continues for an initial term of two years.",
                            citations=[
                                LLMCitationItem(
                                    chunk_id=ch6_id,
                                    page_number=1,
                                    verbatim_quote="initial term of two (2) years",
                                )
                            ],
                        )
                    ],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert len(resp.claims) == 1
        claim = resp.claims[0]
        # Invariant: Must NOT be accepted as grounded
        assert claim.is_grounded is False
        assert claim.citations[0].verification_status == CitationVerificationStatus.WRONG_CONTRACT

    @pytest.mark.asyncio
    async def test_failure_mode_6_text_mismatch_hallucinated_snippet(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 6: Citation verbatim quote does not match chunk text -> TEXT_MISMATCH."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        ch1_id = "aaaa0001-0001-4001-8001-000000000001"
        req = RAGQueryRequest(query="What is the termination notice?")

        provider = MockEvalEmbeddingProvider(default_axis=0)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="Notice period is 90 days.",
                    has_sufficient_evidence=True,
                    claims=[
                        LLMClaimItem(
                            claim="Notice period is 90 days.",
                            citations=[
                                LLMCitationItem(
                                    chunk_id=ch1_id,
                                    page_number=1,
                                    verbatim_quote="terminate for convenience upon ninety (90) days notice",
                                )
                            ],
                        )
                    ],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert len(resp.claims) == 1
        claim = resp.claims[0]
        # Invariant: Must NOT be accepted as grounded
        assert claim.is_grounded is False
        assert claim.citations[0].verification_status == CitationVerificationStatus.TEXT_MISMATCH

    @pytest.mark.asyncio
    async def test_failure_mode_7_page_number_mismatch(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 7: Stated page does not match chunk page -> PAGE_MISMATCH."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        ch5_id = "aaaa0005-0005-4005-8005-000000000005"  # Page 3
        req = RAGQueryRequest(query="What is the governing jurisdiction?")

        provider = MockEvalEmbeddingProvider(default_axis=4)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="Delaware courts have exclusive jurisdiction.",
                    has_sufficient_evidence=True,
                    claims=[
                        LLMClaimItem(
                            claim="Wilmington, Delaware courts possess exclusive jurisdiction.",
                            citations=[
                                LLMCitationItem(
                                    chunk_id=ch5_id,
                                    page_number=99,  # Wrong page number
                                    verbatim_quote="The state and federal courts situated in Wilmington, Delaware shall possess exclusive jurisdiction",
                                )
                            ],
                        )
                    ],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert len(resp.claims) == 1
        claim = resp.claims[0]
        assert claim.is_grounded is False
        assert claim.citations[0].verification_status == CitationVerificationStatus.PAGE_MISMATCH

    @pytest.mark.asyncio
    async def test_failure_mode_8_malformed_llm_output(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 8: Malformed structured LLM output raises RAGServiceError cleanly."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        req = RAGQueryRequest(query="What are the confidentiality terms?")

        provider = MockEvalEmbeddingProvider(default_axis=3)
        llm = MockEvalStructuredLLMProvider(
            failure_mode_map={req.query: "malformed_llm_output"}
        )

        with pytest.raises(RAGServiceError) as exc_info:
            await answer_contract_query_grounded(
                db=db_session,
                contract_id=c1_id,
                request=req,
                embedding_provider=provider,
                llm_provider=llm,
            )
        assert "LLM generation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_failure_mode_9_llm_provider_timeout_failure(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 9: LLM provider network failure/timeout raises RAGServiceError cleanly."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        req = RAGQueryRequest(query="Summarize indemnification scope.")

        provider = MockEvalEmbeddingProvider(default_axis=2)
        llm = MockEvalStructuredLLMProvider(
            failure_mode_map={req.query: "llm_provider_failure"}
        )

        with pytest.raises(RAGServiceError) as exc_info:
            await answer_contract_query_grounded(
                db=db_session,
                contract_id=c1_id,
                request=req,
                embedding_provider=provider,
                llm_provider=llm,
            )
        assert "LLM generation failed" in str(exc_info.value)

    def test_failure_mode_10_empty_context_construction(self):
        """Failure Mode 10: Empty retrieved matches handled gracefully in context construction."""
        context_str, chunk_map = build_grounded_context([])
        assert context_str == ""
        assert chunk_map == {}

    def test_failure_mode_11_conflicting_facts_isolated_by_citations(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 11: Conflicting clauses each receive independent verified citations."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        ch2_id = "aaaa0002-0002-4002-8002-000000000002"

        # General liability cap vs indemnity exception in same chunk
        _, _, _, status1, _ = verify_citation(
            db=db_session,
            contract_id=c1_id,
            chunk_id_str=ch2_id,
            verbatim_quote="strictly capped at the total fees paid",
            page_number=1,
        )
        _, _, _, status2, _ = verify_citation(
            db=db_session,
            contract_id=c1_id,
            chunk_id_str=ch2_id,
            verbatim_quote="Except for indemnification obligations under Section 3",
            page_number=1,
        )
        assert status1 == CitationVerificationStatus.VALID
        assert status2 == CitationVerificationStatus.VALID

    @pytest.mark.asyncio
    async def test_failure_mode_12_missing_extracted_facts(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 12: Fact absent from contract returns insufficient evidence."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        req = RAGQueryRequest(query="What is NovaScale's late payment fee penalty?")

        provider = MockEvalEmbeddingProvider(default_axis=0)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="The NovaScale agreement does not specify any late payment fee penalty.",
                    has_sufficient_evidence=False,
                    claims=[],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert resp.status == RAGStatus.INSUFFICIENT_EVIDENCE
        assert resp.has_sufficient_evidence is False

    @pytest.mark.asyncio
    async def test_failure_mode_13_cross_contract_evidence_contamination(self, setup_evaluation_contracts: GroundedRAGEvaluator, db_session: Session):
        """Failure Mode 13: Contract A claim citing Contract B chunk is rejected as WRONG_CONTRACT."""
        c1_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        ch7_id = "bbbb0002-0002-4002-8002-000000000002"  # Belongs to c2 (Apex)
        req = RAGQueryRequest(query="What are the payment terms?")

        provider = MockEvalEmbeddingProvider(default_axis=0)
        llm = MockEvalStructuredLLMProvider(
            canned_answers={
                req.query: StructuredRAGAnswerLLM(
                    answer="Late payments incur a fee of 1.5% per month.",
                    has_sufficient_evidence=True,
                    claims=[
                        LLMClaimItem(
                            claim="Late payments incur a fee of 1.5% per month.",
                            citations=[
                                LLMCitationItem(
                                    chunk_id=ch7_id,
                                    page_number=1,
                                    verbatim_quote="Late payments incur a fee of 1.5% per month.",
                                )
                            ],
                        )
                    ],
                )
            }
        )

        resp = await answer_contract_query_grounded(
            db=db_session,
            contract_id=c1_id,
            request=req,
            embedding_provider=provider,
            llm_provider=llm,
        )
        assert len(resp.claims) == 1
        claim = resp.claims[0]
        assert claim.is_grounded is False
        assert claim.citations[0].verification_status == CitationVerificationStatus.WRONG_CONTRACT


# ====================================================================
# Phase 17E: Quality Reporting & Threshold Enforcement Tests
# ====================================================================

class TestQualityReportingAndThresholds:
    """Tests evaluating end-to-end report generation and grounding invariant thresholds."""

    @pytest.mark.asyncio
    async def test_grounded_evaluator_end_to_end(self, db_session: Session):
        """
        Executes complete grounded RAG evaluation suite against benchmark dataset.
        Verifies:
          - All cases evaluated deterministically.
          - Invariants adherence meets 100% threshold.
          - Machine-readable JSON report serializes properly.
          - Human-readable Markdown summary formats cleanly.
        """
        evaluator = GroundedRAGEvaluator()

        try:
            # Seed dataset
            evaluator.seed_dataset(db_session)

            # Build deterministic mock providers
            llm_provider = evaluator.build_mock_llm_provider()
            embedding_provider = MockEvalEmbeddingProvider(default_axis=0)

            # Execute evaluation
            report: GroundedEvaluationReport = await evaluator.evaluate_all(
                db=db_session,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
            )

            # Assertions on test suite completion
            assert report.total_cases == len(evaluator.dataset.cases)
            assert report.total_cases >= 16
            assert report.pass_rate >= 0.90

            # Verify critical grounding invariants
            invariants = report.invariants_adherence
            assert invariants["zero_wrong_contract"] is True
            assert invariants["zero_hallucinated_chunks"] is True
            assert invariants["hundred_percent_text_mismatch_flagged"] is True
            assert invariants["hundred_percent_insufficient_evidence"] is True
            assert invariants["hundred_percent_cross_contract_isolated"] is True

            # Verify JSON serialization (machine-readable)
            json_report = report.to_json()
            assert isinstance(json_report, str)
            parsed_json = json.loads(json_report)
            assert parsed_json["dataset_name"] == report.dataset_name
            assert "aggregate_metrics" in parsed_json
            assert "invariants_adherence" in parsed_json

            # Verify Markdown formatting (human-readable)
            markdown_report = report.format_markdown_report()
            assert "# Grounded RAG & Quality Evaluation Report" in markdown_report
            assert "Critical Grounding Invariants Compliance" in markdown_report
            assert "Aggregate Grounding Quality Metrics" in markdown_report
            assert "Detailed Test Case Results" in markdown_report
            assert "PASS" in markdown_report

            print("\n" + markdown_report)

        finally:
            evaluator.cleanup_dataset(db_session)
