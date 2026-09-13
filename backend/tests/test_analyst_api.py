"""
ContractIQ — Tests for AI Analyst API & Multi-Contract RAG (Phase 10A–10E)

Verifies:
  - 10A: Analyst API service foundation & structured response generation.
  - 10B: Single-contract natural language question-answering with hybrid retrieval + citations.
  - 10C: Cross-contract questions with strict per-contract scoping and zero cross-document bleed.
  - 10D: Evidence-backed responses, 6-tier lineage (answer -> claim -> evidence -> chunk -> page -> contract),
         citation validation failure, and flagging unsupported claims.
  - 10E: Retrieval & debug metadata (method, selected chunks, scores/ranks, zero secrets or embeddings).
  - Failure modes: no evidence, insufficient evidence, wrong-contract citations,
         provider failure, malformed structured output, contract scoping enforcement.
  - Zero external LLM calls (fully deterministic mocks).
"""

from typing import Any, Optional, Type
import uuid
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.models.evidence import Evidence
from app.schemas.analyst import (
    AnalystQueryResponse,
    AnalystQueryScope,
    CrossContractAnalystRequest,
    SingleContractAnalystRequest,
)
from app.schemas.rag import (
    CitationVerificationStatus,
    LLMCitationItem,
    LLMClaimItem,
    RAGStatus,
    StructuredRAGAnswerLLM,
)
from app.services.analyst_service import (
    AnalystServiceError,
    ContractScopingError,
    ask_contract_analyst_cross,
    ask_contract_analyst_single,
)
from app.services.embedding_provider import EmbeddingProvider
from app.services.structured_output_provider import (
    StructuredLLMProvider,
    StructuredOutputParseError,
    StructuredOutputProviderError,
)


# ====================================================================
# Mock Providers
# ====================================================================

class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding mock."""

    @property
    def model_name(self) -> str:
        return "mock-gemini-embedding-2"

    @property
    def dimension(self) -> int:
        return 768

    async def embed_texts(
        self,
        texts: list[str],
        task_type: Any = "RETRIEVAL_DOCUMENT",
        title: str | None = None,
    ) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]


class MockStructuredLLMProvider(StructuredLLMProvider):
    """Deterministic structured output LLM mock."""

    def __init__(self, canned_response: Any = None, should_fail: Optional[Exception] = None):
        self._response = canned_response
        self._fail = should_fail

    @property
    def model_name(self) -> str:
        return "mock-gemini-flash"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_instruction: str | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Any:
        if self._fail:
            raise self._fail
        return self._response


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def db_session():
    """Database session fixture."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def multi_contract_setup(db_session: Session):
    """
    Creates two distinct contracts with chunks and persistent evidence records.
    Used for single-contract and cross-contract testing.
    """
    # Contract A: MSA
    contract_a_id = uuid.uuid4()
    contract_a = Contract(
        id=contract_a_id,
        title="Apex Cloud Master Services Agreement",
        vendor="Apex Cloud Inc",
        contract_type="MSA",
        status="active",
        processing_status="completed",
    )
    db_session.add(contract_a)

    chunk_a1_id = uuid.uuid4()
    chunk_a1 = DocumentChunk(
        id=chunk_a1_id,
        contract_id=contract_a_id,
        chunk_index=0,
        page_number=2,
        section_header="Section 4. Termination",
        text="Customer may terminate this Agreement without cause upon providing at least thirty (30) days prior written notice.",
        char_start=0,
        char_end=116,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk_a1)

    evidence_a = Evidence(
        id=uuid.uuid4(),
        contract_id=contract_a_id,
        source_item_type="clause",
        source_item_id=uuid.uuid4(),
        source_chunk_id=chunk_a1_id,
        page_number=2,
        source_text="Customer may terminate this Agreement without cause upon providing at least thirty (30) days prior written notice.",
        char_start=0,
        char_end=116,
    )
    db_session.add(evidence_a)

    # Contract B: Vendor SLA
    contract_b_id = uuid.uuid4()
    contract_b = Contract(
        id=contract_b_id,
        title="Beta Data Analytics SLA",
        vendor="Beta Analytics LLC",
        contract_type="SLA",
        status="active",
        processing_status="completed",
    )
    db_session.add(contract_b)

    chunk_b1_id = uuid.uuid4()
    chunk_b1 = DocumentChunk(
        id=chunk_b1_id,
        contract_id=contract_b_id,
        chunk_index=0,
        page_number=4,
        section_header="Section 9. Term & Termination",
        text="Either party may terminate upon sixty (60) days advance written notice to the registered agent.",
        char_start=0,
        char_end=103,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk_b1)

    evidence_b = Evidence(
        id=uuid.uuid4(),
        contract_id=contract_b_id,
        source_item_type="clause",
        source_item_id=uuid.uuid4(),
        source_chunk_id=chunk_b1_id,
        page_number=4,
        source_text="Either party may terminate upon sixty (60) days advance written notice to the registered agent.",
        char_start=0,
        char_end=103,
    )
    db_session.add(evidence_b)

    db_session.commit()

    data = {
        "contract_a": contract_a,
        "chunk_a1": chunk_a1,
        "evidence_a": evidence_a,
        "contract_b": contract_b,
        "chunk_b1": chunk_b1,
        "evidence_b": evidence_b,
    }

    yield data

    # Cleanup
    db_session.query(Evidence).filter(Evidence.contract_id.in_([contract_a_id, contract_b_id])).delete()
    db_session.query(DocumentChunk).filter(DocumentChunk.contract_id.in_([contract_a_id, contract_b_id])).delete()
    db_session.query(Contract).filter(Contract.id.in_([contract_a_id, contract_b_id])).delete()
    db_session.commit()


# ====================================================================
# Unit & Integration Tests: Single-Contract Analysis (10B, 10D, 10E)
# ====================================================================

class TestSingleContractAnalyst:
    """Test suite for single contract inquiries."""

    @pytest.mark.asyncio
    async def test_single_contract_question_with_citations_and_debug(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """10B & 10E: Verifies grounded single-contract inquiry with verified citations and debug metadata."""
        contract = multi_contract_setup["contract_a"]
        chunk = multi_contract_setup["chunk_a1"]

        canned = StructuredRAGAnswerLLM(
            has_sufficient_evidence=True,
            answer="Customer may terminate for convenience with 30 days prior written notice.",
            claims=[
                LLMClaimItem(
                    claim="Termination for convenience requires 30 days prior written notice.",
                    citations=[
                        LLMCitationItem(
                            chunk_id=str(chunk.id),
                            page_number=2,
                            verbatim_quote="Customer may terminate this Agreement without cause upon providing at least thirty (30) days prior written notice.",
                        )
                    ],
                )
            ],
        )

        request = SingleContractAnalystRequest(
            query="What is the notice period for termination?",
            top_k=3,
            include_debug=True,
        )

        resp = await ask_contract_analyst_single(
            db=db_session,
            contract_id=contract.id,
            request=request,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=MockStructuredLLMProvider(canned_response=canned),
        )

        assert resp.scope == AnalystQueryScope.SINGLE_CONTRACT
        assert resp.status == RAGStatus.ANSWERED
        assert resp.has_sufficient_evidence is True
        assert resp.confidence_score >= 0.9
        assert len(resp.claims) == 1
        claim = resp.claims[0]
        assert claim.is_grounded is True
        assert len(claim.citations) == 1
        citation = claim.citations[0]
        assert citation.verification_status == CitationVerificationStatus.VALID
        assert citation.contract_id == contract.id
        assert citation.chunk_id == chunk.id
        assert citation.page_number == 2
        assert citation.evidence_id is not None  # Linked to persistent evidence

        # 10E: Debug metadata verification
        assert resp.debug_info is not None
        assert resp.debug_info.retrieval_method == "hybrid_rrf"
        assert resp.debug_info.total_contracts_searched == 1
        assert len(resp.debug_info.selected_chunks) > 0
        # Zero secret or embedding exposure
        debug_chunk = resp.debug_info.selected_chunks[0]
        assert hasattr(debug_chunk, "hybrid_score")
        assert not hasattr(debug_chunk, "embedding")

    @pytest.mark.asyncio
    async def test_single_contract_no_evidence_handles_gracefully(
        self, db_session: Session
    ):
        """Tests no-matches scenario for contract with 0 chunks."""
        empty_contract_id = uuid.uuid4()
        empty_contract = Contract(
            id=empty_contract_id,
            title="Empty Test Agreement",
            status="active",
            processing_status="completed",
        )
        db_session.add(empty_contract)
        db_session.commit()

        try:
            req = SingleContractAnalystRequest(
                query="What is the governing law?",
                include_debug=True,
            )
            resp = await ask_contract_analyst_single(
                db=db_session,
                contract_id=empty_contract_id,
                request=req,
                embedding_provider=MockEmbeddingProvider(),
                llm_provider=MockStructuredLLMProvider(canned_response=None),
            )
            assert resp.status == RAGStatus.NO_RETRIEVAL_MATCHES
            assert resp.has_sufficient_evidence is False
            assert "No relevant clauses" in resp.answer
            assert resp.total_citations == 0
        finally:
            db_session.delete(empty_contract)
            db_session.commit()

    @pytest.mark.asyncio
    async def test_single_contract_insufficient_evidence_response(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """Tests explicit LLM-detected insufficient evidence response."""
        contract = multi_contract_setup["contract_a"]
        canned = StructuredRAGAnswerLLM(
            has_sufficient_evidence=False,
            answer="The contract does not specify indemnification limits for IP infringement.",
            claims=[],
        )

        req = SingleContractAnalystRequest(
            query="What is the indemnification liability cap?",
        )
        resp = await ask_contract_analyst_single(
            db=db_session,
            contract_id=contract.id,
            request=req,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=MockStructuredLLMProvider(canned_response=canned),
        )

        assert resp.status == RAGStatus.INSUFFICIENT_EVIDENCE
        assert resp.has_sufficient_evidence is False
        assert resp.confidence_score == 0.2
        assert len(resp.claims) == 0


# ====================================================================
# Unit & Integration Tests: Cross-Contract Analysis (10C, 10D)
# ====================================================================

class TestCrossContractAnalyst:
    """Test suite for comparative and cross-contract inquiries."""

    @pytest.mark.asyncio
    async def test_cross_contract_comparative_question(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """10C & 10D: Tests comparative query across two distinct contracts."""
        ca = multi_contract_setup["contract_a"]
        cb = multi_contract_setup["contract_b"]
        chunk_a = multi_contract_setup["chunk_a1"]
        chunk_b = multi_contract_setup["chunk_b1"]

        canned = StructuredRAGAnswerLLM(
            has_sufficient_evidence=True,
            answer="Apex Cloud requires 30 days termination notice, whereas Beta Data requires 60 days.",
            claims=[
                LLMClaimItem(
                    claim="Apex Cloud requires 30 days prior written notice.",
                    citations=[
                        LLMCitationItem(
                            chunk_id=str(chunk_a.id),
                            page_number=2,
                            verbatim_quote="Customer may terminate this Agreement without cause upon providing at least thirty (30) days prior written notice.",
                        )
                    ],
                ),
                LLMClaimItem(
                    claim="Beta Data requires 60 days advance written notice.",
                    citations=[
                        LLMCitationItem(
                            chunk_id=str(chunk_b.id),
                            page_number=4,
                            verbatim_quote="Either party may terminate upon sixty (60) days advance written notice to the registered agent.",
                        )
                    ],
                ),
            ],
        )

        req = CrossContractAnalystRequest(
            contract_ids=[ca.id, cb.id],
            query="Compare the termination notice periods between both contracts.",
            top_k_per_contract=3,
            include_debug=True,
        )

        resp = await ask_contract_analyst_cross(
            db=db_session,
            request=req,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=MockStructuredLLMProvider(canned_response=canned),
        )

        assert resp.scope == AnalystQueryScope.CROSS_CONTRACT
        assert resp.status == RAGStatus.ANSWERED
        assert resp.has_sufficient_evidence is True
        assert len(resp.claims) == 2

        claim_a = resp.claims[0]
        assert claim_a.contract_id == ca.id
        assert claim_a.citations[0].verification_status == CitationVerificationStatus.VALID
        assert claim_a.citations[0].contract_id == ca.id
        assert claim_a.citations[0].page_number == 2

        claim_b = resp.claims[1]
        assert claim_b.contract_id == cb.id
        assert claim_b.citations[0].verification_status == CitationVerificationStatus.VALID
        assert claim_b.citations[0].contract_id == cb.id
        assert claim_b.citations[0].page_number == 4

        # Debug metadata
        assert resp.debug_info is not None
        assert resp.debug_info.retrieval_method == "cross_contract_hybrid_rrf"
        assert resp.debug_info.total_contracts_searched == 2

    @pytest.mark.asyncio
    async def test_cross_contract_scoping_nonexistent_contract_raises(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """10C: Enforces strict contract scoping: non-existent contract ID raises ContractScopingError."""
        ca = multi_contract_setup["contract_a"]
        fake_id = uuid.uuid4()

        req = CrossContractAnalystRequest(
            contract_ids=[ca.id, fake_id],
            query="Compare notice periods.",
        )

        with pytest.raises(ContractScopingError) as exc_info:
            await ask_contract_analyst_cross(
                db=db_session,
                request=req,
                embedding_provider=MockEmbeddingProvider(),
                llm_provider=MockStructuredLLMProvider(canned_response=None),
            )
        assert "do not exist or are inaccessible" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cross_contract_wrong_contract_citation_flagged(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """10D: If citation references a chunk belonging to an unqueried contract, flag WRONG_CONTRACT."""
        ca = multi_contract_setup["contract_a"]
        cb = multi_contract_setup["contract_b"]

        # Create a third unqueried contract
        unqueried_id = uuid.uuid4()
        unqueried_c = Contract(
            id=unqueried_id,
            title="Unrelated Secret Agreement",
            status="active",
            processing_status="completed",
        )
        db_session.add(unqueried_c)
        unqueried_chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=unqueried_id,
            chunk_index=0,
            page_number=1,
            text="Unrelated confidential text here.",
            char_start=0,
            char_end=32,
            embedding=[0.1] * 768,
        )
        db_session.add(unqueried_chunk)
        db_session.commit()

        try:
            # LLM cites the unqueried contract's chunk
            canned = StructuredRAGAnswerLLM(
                has_sufficient_evidence=True,
                answer="Misattributed finding.",
                claims=[
                    LLMClaimItem(
                        claim="Misattributed finding from unqueried agreement.",
                        citations=[
                            LLMCitationItem(
                                chunk_id=str(unqueried_chunk.id),
                                page_number=1,
                                verbatim_quote="Unrelated confidential text here.",
                            )
                        ],
                    )
                ],
            )

            req = CrossContractAnalystRequest(
                contract_ids=[ca.id, cb.id],
                query="Check terms.",
            )

            resp = await ask_contract_analyst_cross(
                db=db_session,
                request=req,
                embedding_provider=MockEmbeddingProvider(),
                llm_provider=MockStructuredLLMProvider(canned_response=canned),
            )

            citation = resp.claims[0].citations[0]
            assert citation.verification_status == CitationVerificationStatus.WRONG_CONTRACT
            assert "not in the queried contracts" in citation.verification_notes
            assert resp.claims[0].is_grounded is False
            assert resp.invalid_citations_count == 1
        finally:
            db_session.delete(unqueried_chunk)
            db_session.delete(unqueried_c)
            db_session.commit()


# ====================================================================
# Unit & Integration Tests: Failure Modes & Edge Cases
# ====================================================================

class TestAnalystFailureModes:
    """Tests failure handling, provider errors, and validation rejections."""

    @pytest.mark.asyncio
    async def test_citation_validation_text_mismatch(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """10D: Flag TEXT_MISMATCH when cited quote is hallucinated/not in chunk."""
        ca = multi_contract_setup["contract_a"]
        chunk_a = multi_contract_setup["chunk_a1"]

        canned = StructuredRAGAnswerLLM(
            has_sufficient_evidence=True,
            answer="Termination is strictly prohibited at all times.",
            claims=[
                LLMClaimItem(
                    claim="Termination is prohibited.",
                    citations=[
                        LLMCitationItem(
                            chunk_id=str(chunk_a.id),
                            page_number=2,
                            verbatim_quote="Neither party shall ever have any right to terminate this Agreement under any circumstances whatsoever.",
                        )
                    ],
                )
            ],
        )

        req = SingleContractAnalystRequest(query="Can I terminate?")
        resp = await ask_contract_analyst_single(
            db=db_session,
            contract_id=ca.id,
            request=req,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=MockStructuredLLMProvider(canned_response=canned),
        )

        citation = resp.claims[0].citations[0]
        assert citation.verification_status == CitationVerificationStatus.TEXT_MISMATCH
        assert resp.claims[0].is_grounded is False
        assert resp.invalid_citations_count == 1
        assert resp.valid_citations_count == 0

    @pytest.mark.asyncio
    async def test_llm_provider_failure_raises_analyst_error(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """Verifies upstream provider errors are safely caught and wrapped in AnalystServiceError."""
        ca = multi_contract_setup["contract_a"]
        req = SingleContractAnalystRequest(query="Explain termination.")

        with pytest.raises(AnalystServiceError) as exc_info:
            await ask_contract_analyst_single(
                db=db_session,
                contract_id=ca.id,
                request=req,
                embedding_provider=MockEmbeddingProvider(),
                llm_provider=MockStructuredLLMProvider(
                    should_fail=StructuredOutputProviderError("Gemini quota exceeded 429")
                ),
            )
        assert "LLM generation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_structured_output_failure(
        self, db_session: Session, multi_contract_setup: dict
    ):
        """Verifies parse failure of structured LLM output is wrapped in AnalystServiceError."""
        ca = multi_contract_setup["contract_a"]
        req = SingleContractAnalystRequest(query="Explain termination.")

        with pytest.raises(AnalystServiceError) as exc_info:
            await ask_contract_analyst_single(
                db=db_session,
                contract_id=ca.id,
                request=req,
                embedding_provider=MockEmbeddingProvider(),
                llm_provider=MockStructuredLLMProvider(
                    should_fail=StructuredOutputParseError("Failed to parse JSON")
                ),
            )
        assert "LLM generation failed" in str(exc_info.value)


# ====================================================================
# REST API Endpoint Tests via TestClient
# ====================================================================

def test_analyst_api_endpoints_mounted():
    """Verifies FastAPI routes /analyst/query and /contracts/{id}/query are correctly mounted."""
    client = TestClient(app)

    # 1. Unknown contract returns 404
    fake_id = uuid.uuid4()
    resp = client.post(
        f"/analyst/contracts/{fake_id}/query",
        json={"query": "What is the term?"},
    )
    assert resp.status_code == 404

    # 2. Universal query with non-existent contract returns 404
    resp2 = client.post(
        "/analyst/query",
        json={
            "contract_ids": [str(fake_id), str(uuid.uuid4())],
            "query": "Compare agreements.",
        },
    )
    assert resp2.status_code == 404

    # 3. Cross query with single contract triggers validation error (< 2 contracts)
    resp3 = client.post(
        "/analyst/query/cross",
        json={
            "contract_ids": [str(fake_id)],
            "query": "Compare.",
        },
    )
    assert resp3.status_code == 422  # Pydantic min_length=2 validation
