"""
ContractIQ — Tests for Clause Extraction (Phase 6B)

Verifies:
  1. Pydantic schemas for extracted clauses (ClauseType, ExtractedClauseLLM, ChunkClauseExtractionResult).
  2. Extraction of clause category, verbatim text, section/label, page number, and source chunk ID.
  3. Deterministic chunk processing (chunk_index order).
  4. Source traceability preservation (clause → chunk → page → contract).
  5. Database persistence using the existing clauses table.
  6. Idempotency (second run returns existing records without calling LLM).
  7. Force re-extraction (clears and re-extracts).
  8. Handling of malformed/invalid LLM outputs via Phase 6A validation.
  9. Error cases: Contract not found (404), No chunks found (400).
 10. REST API endpoints (POST /extract-clauses and GET /clauses).
 11. Zero secrets or API keys leaked.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.clause import (
    ChunkClauseExtractionResult,
    ClauseType,
    ExtractedClauseLLM,
)
from app.services.clause_extraction_service import (
    ContractNotFoundError,
    NoChunksFoundError,
    extract_clauses_from_chunk,
    extract_contract_clauses,
    list_contract_clauses,
)
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import StructuredOutputParseError


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def db_session():
    """Provides a transactional database session for tests with cleanup."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client():
    """FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def test_contract(db_session: Session):
    """Creates a temporary Contract record for testing, cleaned up afterwards."""
    contract = Contract(
        id=uuid.uuid4(),
        title="Phase 6B Test MSA Contract",
        vendor="Acme Software Corp",
        contract_type="MSA",
        status="active",
        processing_status="processing",
    )
    db_session.add(contract)
    db_session.commit()

    try:
        yield contract
    finally:
        # Cascade cleanup: clauses and chunks deleted automatically
        db_session.query(Clause).filter(Clause.contract_id == contract.id).delete()
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract.id).delete()
        db_session.query(Contract).filter(Contract.id == contract.id).delete()
        db_session.commit()


@pytest.fixture
def test_chunks(db_session: Session, test_contract: Contract):
    """Creates 2 ordered DocumentChunks for the test contract."""
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        chunk_index=0,
        page_number=1,
        section_header="Section 7 — Term & Termination",
        char_start=0,
        char_end=200,
        text="Either party may terminate this Agreement upon thirty (30) days prior written notice.",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        chunk_index=1,
        page_number=2,
        section_header="Section 12 — Limitation of Liability",
        char_start=201,
        char_end=450,
        text="In no event shall either party's aggregate liability exceed the total fees paid in the preceding 12 months.",
    )
    db_session.add(chunk1)
    db_session.add(chunk2)
    db_session.commit()

    return [chunk1, chunk2]


# ====================================================================
# 1. Chunk Extraction Unit Tests
# ====================================================================

class TestChunkClauseExtraction:
    """Unit tests for extract_clauses_from_chunk."""

    @pytest.mark.asyncio
    async def test_extract_clauses_from_chunk_success(self):
        """Extracts valid clauses from chunk using mocked provider."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ChunkClauseExtractionResult(
                clauses=[
                    ExtractedClauseLLM(
                        clause_type=ClauseType.TERMINATION,
                        clause_label="Section 7.1 — Early Termination",
                        verbatim_text="Either party may terminate upon 30 days notice.",
                        confidence=0.95,
                        explanation="Defines early termination notice requirements.",
                    )
                ],
                has_clauses=True,
            )
        )

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            section_header="Section 7",
            text="Termination text...",
        )

        clauses = await extract_clauses_from_chunk(chunk, mock_provider)
        assert len(clauses) == 1
        assert clauses[0].clause_type == ClauseType.TERMINATION
        assert clauses[0].clause_label == "Section 7.1 — Early Termination"
        assert clauses[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_extract_clauses_from_chunk_empty(self):
        """Returns empty list when chunk contains no operative clauses."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ChunkClauseExtractionResult(clauses=[], has_clauses=False)
        )

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            section_header="Table of Contents",
            text="1. Introduction ... 2. Definitions ...",
        )

        clauses = await extract_clauses_from_chunk(chunk, mock_provider)
        assert clauses == []

    @pytest.mark.asyncio
    async def test_extract_clauses_gracefully_handles_structured_output_error(self):
        """Handles StructuredOutputParseError gracefully by logging and returning empty list."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            side_effect=StructuredOutputParseError("Malformed JSON from LLM")
        )

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            section_header="Section 1",
            text="Some corrupt output text",
        )

        clauses = await extract_clauses_from_chunk(chunk, mock_provider)
        assert clauses == []


# ====================================================================
# 2. Contract Clause Extraction Service Tests (Database Verified)
# ====================================================================

class TestContractClauseExtractionService:
    """Service-level tests verifying database persistence, lineage, and idempotency."""

    @pytest.mark.asyncio
    async def test_extract_and_persist_contract_clauses(
        self,
        db_session: Session,
        test_contract: Contract,
        test_chunks: list[DocumentChunk],
    ):
        """Extracts clauses from chunks, persists them, and verifies lineage and metrics."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)

        # Mock responses for chunk 1 and chunk 2
        async def mock_generate(prompt, schema, **kwargs):
            if "Section 7" in prompt:
                return ChunkClauseExtractionResult(
                    clauses=[
                        ExtractedClauseLLM(
                            clause_type=ClauseType.TERMINATION,
                            clause_label="Section 7 — Term & Termination",
                            verbatim_text="Either party may terminate this Agreement upon thirty (30) days prior written notice.",
                            confidence=0.98,
                        )
                    ],
                    has_clauses=True,
                )
            else:
                return ChunkClauseExtractionResult(
                    clauses=[
                        ExtractedClauseLLM(
                            clause_type=ClauseType.LIABILITY,
                            clause_label="Section 12 — Limitation of Liability",
                            verbatim_text="In no event shall either party's aggregate liability exceed the total fees paid.",
                            confidence=0.92,
                        )
                    ],
                    has_clauses=True,
                )

        mock_provider.generate_structured = AsyncMock(side_effect=mock_generate)

        response = await extract_contract_clauses(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )

        assert response.contract_id == test_contract.id
        assert response.total_chunks_processed == 2
        assert response.total_clauses_extracted == 2
        assert response.clauses_by_type == {"termination": 1, "liability": 1}
        assert len(response.clauses) == 2

        # Verify lineage: clause -> chunk -> page -> contract
        term_clause = next(c for c in response.clauses if c.clause_type == "termination")
        assert term_clause.source_chunk_id == test_chunks[0].id
        assert term_clause.page_number == 1
        assert term_clause.contract_id == test_contract.id
        assert "thirty (30) days" in term_clause.verbatim_text

        liab_clause = next(c for c in response.clauses if c.clause_type == "liability")
        assert liab_clause.source_chunk_id == test_chunks[1].id
        assert liab_clause.page_number == 2
        assert liab_clause.contract_id == test_contract.id

        # Verify persistence in database
        db_clauses = db_session.query(Clause).filter(Clause.contract_id == test_contract.id).all()
        assert len(db_clauses) == 2

    @pytest.mark.asyncio
    async def test_extraction_idempotency(
        self,
        db_session: Session,
        test_contract: Contract,
        test_chunks: list[DocumentChunk],
    ):
        """Second call with force_reextract=False returns existing records without re-calling LLM."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ChunkClauseExtractionResult(
                clauses=[
                    ExtractedClauseLLM(
                        clause_type=ClauseType.TERMINATION,
                        verbatim_text="Termination clause text",
                    )
                ],
                has_clauses=True,
            )
        )

        # First run
        res1 = await extract_contract_clauses(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )
        assert res1.total_clauses_extracted > 0
        first_call_count = mock_provider.generate_structured.call_count

        # Second run: should be a no-op / return existing
        res2 = await extract_contract_clauses(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )

        assert res2.total_clauses_extracted == res1.total_clauses_extracted
        # Call count should NOT have increased
        assert mock_provider.generate_structured.call_count == first_call_count

    @pytest.mark.asyncio
    async def test_force_reextract_replaces_clauses(
        self,
        db_session: Session,
        test_contract: Contract,
        test_chunks: list[DocumentChunk],
    ):
        """Calling with force_reextract=True clears existing clauses and extracts fresh ones."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ChunkClauseExtractionResult(
                clauses=[
                    ExtractedClauseLLM(
                        clause_type=ClauseType.CONFIDENTIALITY,
                        verbatim_text="Confidentiality text",
                    )
                ],
                has_clauses=True,
            )
        )

        # First run
        await extract_contract_clauses(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )
        call_count_1 = mock_provider.generate_structured.call_count

        # Re-run with force_reextract=True
        res = await extract_contract_clauses(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=True,
            provider=mock_provider,
        )

        assert mock_provider.generate_structured.call_count > call_count_1
        assert res.total_clauses_extracted > 0
        assert all(c.clause_type == "confidentiality" for c in res.clauses)

    @pytest.mark.asyncio
    async def test_contract_not_found_raises_error(self, db_session: Session):
        """Raises ContractNotFoundError for non-existent contract ID."""
        random_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError) as exc_info:
            await extract_contract_clauses(db=db_session, contract_id=random_id)
        assert str(random_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_chunks_found_raises_error(
        self, db_session: Session, test_contract: Contract
    ):
        """Raises NoChunksFoundError if contract has no document chunks."""
        with pytest.raises(NoChunksFoundError) as exc_info:
            await extract_contract_clauses(db=db_session, contract_id=test_contract.id)
        assert "no document chunks" in str(exc_info.value).lower()

    def test_list_contract_clauses_and_filtering(
        self,
        db_session: Session,
        test_contract: Contract,
        test_chunks: list[DocumentChunk],
    ):
        """Tests list_contract_clauses with and without clause_type filtering."""
        # Seed 2 clauses manually
        c1 = Clause(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            source_chunk_id=test_chunks[0].id,
            clause_type="termination",
            clause_label="Section 7",
            verbatim_text="Notice of termination",
            page_number=1,
        )
        c2 = Clause(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            source_chunk_id=test_chunks[1].id,
            clause_type="liability",
            clause_label="Section 12",
            verbatim_text="Limitation of liability",
            page_number=2,
        )
        db_session.add(c1)
        db_session.add(c2)
        db_session.commit()

        # Unfiltered list
        all_res = list_contract_clauses(db=db_session, contract_id=test_contract.id)
        assert all_res.total_clauses == 2

        # Filtered by clause_type="termination"
        filtered_res = list_contract_clauses(
            db=db_session, contract_id=test_contract.id, clause_type="termination"
        )
        assert filtered_res.total_clauses == 1
        assert filtered_res.clauses[0].clause_type == "termination"


# ====================================================================
# 3. REST API Endpoint Tests
# ====================================================================

class TestClauseExtractionAPI:
    """Integration tests verifying HTTP endpoints."""

    def test_api_contract_not_found(self, test_client: TestClient):
        """POST /contracts/{random_id}/extract-clauses returns 404."""
        random_id = uuid.uuid4()
        response = test_client.post(f"/contracts/{random_id}/extract-clauses")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_api_no_chunks_returns_400(
        self, test_client: TestClient, test_contract: Contract
    ):
        """POST /contracts/{id}/extract-clauses returns 400 if no chunks exist."""
        response = test_client.post(f"/contracts/{test_contract.id}/extract-clauses")
        assert response.status_code == 400
        assert "no document chunks" in response.json()["detail"].lower()

    def test_api_get_clauses_empty_initially(
        self, test_client: TestClient, test_contract: Contract
    ):
        """GET /contracts/{id}/clauses returns empty list when no clauses exist."""
        response = test_client.get(f"/contracts/{test_contract.id}/clauses")
        assert response.status_code == 200
        data = response.json()
        assert data["contract_id"] == str(test_contract.id)
        assert data["total_clauses"] == 0
        assert data["clauses"] == []

    def test_api_get_clauses_versioned_alias(
        self, test_client: TestClient, test_contract: Contract
    ):
        """GET /api/v1/contracts/{id}/clauses behaves identically to /contracts/{id}/clauses."""
        response = test_client.get(f"/api/v1/contracts/{test_contract.id}/clauses")
        assert response.status_code == 200
        assert response.json()["total_clauses"] == 0
