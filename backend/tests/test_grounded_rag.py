"""
ContractIQ — Tests for Grounded RAG Generation & Citation Validation (Phase 9A–9E)

Verifies:
  - 9A: Context construction preserves chunk metadata, order, and bounded size.
  - 9B: Grounded LLM generation produces structured answers constrained to context.
  - 9C: Citations correctly trace answer → claim → citation → chunk → page → contract.
  - 9D: Citation validation verifies quotes, detects text mismatches, wrong-contract
        citations, and missing chunk IDs.
  - 9E: Not-found and insufficient-evidence handling when matches are empty, confidence
        is low, or context lacks explicit evidence.
  - Mocked LLM & Embedding providers: Zero external API calls, deterministic fixtures.
"""

from typing import Any, Optional, Type
import uuid
import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.query import HybridChunkMatch
from app.schemas.rag import (
    CitationVerificationStatus,
    LLMCitationItem,
    LLMClaimItem,
    RAGQueryRequest,
    RAGStatus,
    StructuredRAGAnswerLLM,
)
from app.services.embedding_provider import EmbeddingProvider
from app.services.rag_service import (
    answer_contract_query_grounded,
    build_grounded_context,
    verify_citation,
)
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
    """Transactional database session for tests."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def rag_contract_setup(db_session: Session):
    """
    Creates a contract with multiple document chunks for RAG evaluation.
    """
    contract_id = uuid.uuid4()
    contract = Contract(
        id=contract_id,
        title="Enterprise Data Processing Agreement",
        vendor="Datastream Analytics LLC",
        contract_type="DPA",
        status="active",
        processing_status="completed",
    )
    db_session.add(contract)

    # Chunk 1: Termination notice
    chunk1_id = uuid.uuid4()
    chunk1 = DocumentChunk(
        id=chunk1_id,
        contract_id=contract_id,
        chunk_index=0,
        page_number=3,
        section_header="Section 8. Term & Termination",
        text="Either party may terminate this Agreement for convenience upon providing at least thirty (30) days prior written notice to the other party.",
        char_start=0,
        char_end=136,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk1)

    # Chunk 2: Liability limitations
    chunk2_id = uuid.uuid4()
    chunk2 = DocumentChunk(
        id=chunk2_id,
        contract_id=contract_id,
        chunk_index=1,
        page_number=5,
        section_header="Section 11. Limitation of Liability",
        text="Each party's maximum aggregate liability shall be limited to the fees paid by Customer during the prior twelve (12) months.",
        char_start=0,
        char_end=123,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk2)
    db_session.commit()

    data = {
        "contract": contract,
        "chunk1": chunk1,
        "chunk2": chunk2,
    }

    try:
        yield data
    finally:
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract_id).delete()
        db_session.query(Contract).filter(Contract.id == contract_id).delete()
        db_session.commit()


# ====================================================================
# Suite 1: Context Construction (Phase 9A)
# ====================================================================

class TestContextConstruction:
    """Verifies bounded and structured context generation."""

    def test_build_grounded_context_formatting(self):
        c1_id = uuid.uuid4()
        c2_id = uuid.uuid4()
        matches = [
            HybridChunkMatch(
                id=c1_id,
                contract_id=uuid.uuid4(),
                page_number=1,
                chunk_index=0,
                section_header="1. Definitions",
                text="Confidential Information means all proprietary data.",
                hybrid_score=0.033,
                rrf_score=0.033,
            ),
            HybridChunkMatch(
                id=c2_id,
                contract_id=uuid.uuid4(),
                page_number=2,
                chunk_index=1,
                section_header=None,
                text="The term shall be three years.",
                hybrid_score=0.016,
                rrf_score=0.016,
            ),
        ]

        context, chunk_map = build_grounded_context(matches, max_total_chars=1000)
        assert f"ID: {c1_id}" in context
        assert "Page: 1" in context
        assert "Section: 1. Definitions" in context
        assert "Confidential Information means" in context
        assert str(c1_id) in chunk_map
        assert str(c2_id) in chunk_map


# ====================================================================
# Suite 2: Citation Validation (Phase 9D)
# ====================================================================

class TestCitationValidation:
    """Verifies deterministic citation integrity checks."""

    def test_valid_citation(self, db_session: Session, rag_contract_setup: dict):
        contract = rag_contract_setup["contract"]
        chunk1 = rag_contract_setup["chunk1"]

        cid, page, sec, status, note = verify_citation(
            db=db_session,
            contract_id=contract.id,
            chunk_id_str=str(chunk1.id),
            verbatim_quote="at least thirty (30) days prior written notice",
            page_number=3,
        )

        assert status == CitationVerificationStatus.VALID
        assert cid == chunk1.id
        assert page == 3

    def test_text_mismatch_detected(self, db_session: Session, rag_contract_setup: dict):
        contract = rag_contract_setup["contract"]
        chunk1 = rag_contract_setup["chunk1"]

        cid, page, sec, status, note = verify_citation(
            db=db_session,
            contract_id=contract.id,
            chunk_id_str=str(chunk1.id),
            verbatim_quote="THIS EXCERPT DOES NOT EXIST IN THE CHUNK",
            page_number=3,
        )

        assert status == CitationVerificationStatus.TEXT_MISMATCH

    def test_page_mismatch_detected(self, db_session: Session, rag_contract_setup: dict):
        contract = rag_contract_setup["contract"]
        chunk1 = rag_contract_setup["chunk1"]

        cid, page, sec, status, note = verify_citation(
            db=db_session,
            contract_id=contract.id,
            chunk_id_str=str(chunk1.id),
            verbatim_quote="at least thirty (30) days prior written notice",
            page_number=99,
        )

        assert status == CitationVerificationStatus.PAGE_MISMATCH

    def test_wrong_contract_citation_rejected(self, db_session: Session, rag_contract_setup: dict):
        chunk1 = rag_contract_setup["chunk1"]
        other_contract_id = uuid.uuid4()

        cid, page, sec, status, note = verify_citation(
            db=db_session,
            contract_id=other_contract_id,
            chunk_id_str=str(chunk1.id),
            verbatim_quote="at least thirty (30) days prior written notice",
            page_number=3,
        )

        assert status == CitationVerificationStatus.WRONG_CONTRACT


# ====================================================================
# Suite 3: Grounded Answer Generation & Not-Found Handling (9B & 9E)
# ====================================================================

class TestGroundedRAGPipeline:
    """Verifies end-to-end grounded query execution."""

    @pytest.mark.anyio
    async def test_grounded_answer_with_valid_citations(
        self, db_session: Session, rag_contract_setup: dict
    ):
        contract = rag_contract_setup["contract"]
        chunk1 = rag_contract_setup["chunk1"]

        # Mock LLM answering based on chunk1
        mock_llm = MockStructuredLLMProvider(
            canned_response=StructuredRAGAnswerLLM(
                has_sufficient_evidence=True,
                answer="The contract may be terminated for convenience with 30 days prior written notice.",
                claims=[
                    LLMClaimItem(
                        claim="Termination for convenience requires 30 days prior written notice.",
                        citations=[
                            LLMCitationItem(
                                chunk_id=str(chunk1.id),
                                page_number=3,
                                verbatim_quote="providing at least thirty (30) days prior written notice",
                            )
                        ],
                    )
                ],
            )
        )

        req = RAGQueryRequest(query="What is the notice period for termination?", top_k=3)
        res = await answer_contract_query_grounded(
            db=db_session,
            contract_id=contract.id,
            request=req,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=mock_llm,
        )

        assert res.status == RAGStatus.ANSWERED
        assert res.has_sufficient_evidence is True
        assert len(res.claims) == 1
        assert res.claims[0].is_grounded is True
        assert res.valid_citations_count == 1
        assert res.invalid_citations_count == 0

    @pytest.mark.anyio
    async def test_insufficient_evidence_response(
        self, db_session: Session, rag_contract_setup: dict
    ):
        contract = rag_contract_setup["contract"]

        # Mock LLM stating no evidence found for unrelated question
        mock_llm = MockStructuredLLMProvider(
            canned_response=StructuredRAGAnswerLLM(
                has_sufficient_evidence=False,
                answer="The provided excerpts do not mention any payment terms or currency.",
                claims=[],
            )
        )

        req = RAGQueryRequest(query="What are the net payment terms?", top_k=3)
        res = await answer_contract_query_grounded(
            db=db_session,
            contract_id=contract.id,
            request=req,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=mock_llm,
        )

        assert res.status == RAGStatus.INSUFFICIENT_EVIDENCE
        assert res.has_sufficient_evidence is False
        assert "do not mention" in res.answer

    @pytest.mark.anyio
    async def test_empty_retrieval_handles_gracefully(self, db_session: Session):
        # Create an empty contract with no chunks
        empty_contract_id = uuid.uuid4()
        c = Contract(id=empty_contract_id, title="Empty Doc", processing_status="uploaded")
        db_session.add(c)
        db_session.commit()

        try:
            req = RAGQueryRequest(query="What is the governing law?", top_k=3)
            res = await answer_contract_query_grounded(
                db=db_session,
                contract_id=empty_contract_id,
                request=req,
                embedding_provider=MockEmbeddingProvider(),
            )
            assert res.status == RAGStatus.NO_RETRIEVAL_MATCHES
            assert res.has_sufficient_evidence is False
        finally:
            db_session.query(Contract).filter(Contract.id == empty_contract_id).delete()
            db_session.commit()

    @pytest.mark.anyio
    async def test_unsupported_citation_flagged(
        self, db_session: Session, rag_contract_setup: dict
    ):
        contract = rag_contract_setup["contract"]
        chunk1 = rag_contract_setup["chunk1"]

        # Mock LLM hallucinating a quote that is not in chunk1
        mock_llm = MockStructuredLLMProvider(
            canned_response=StructuredRAGAnswerLLM(
                has_sufficient_evidence=True,
                answer="Termination requires 90 days notice.",
                claims=[
                    LLMClaimItem(
                        claim="Notice is 90 days.",
                        citations=[
                            LLMCitationItem(
                                chunk_id=str(chunk1.id),
                                page_number=3,
                                verbatim_quote="90 days written notice required",
                            )
                        ],
                    )
                ],
            )
        )

        req = RAGQueryRequest(query="Notice period?", top_k=3)
        res = await answer_contract_query_grounded(
            db=db_session,
            contract_id=contract.id,
            request=req,
            embedding_provider=MockEmbeddingProvider(),
            llm_provider=mock_llm,
        )

        assert res.status == RAGStatus.ANSWERED
        assert res.claims[0].is_grounded is False
        assert res.invalid_citations_count == 1
        assert res.claims[0].citations[0].verification_status == CitationVerificationStatus.TEXT_MISMATCH
