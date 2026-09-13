"""
ContractIQ — Tests for Contract Fact Extraction (Phase 6D)

Verifies:
  1. Pydantic schemas for extracted facts (FactKey, ExtractedFactLLM, ClauseFactExtractionResult).
  2. Extraction of contract facts: effective date, expiration date, payment terms, currency,
     parties, governing law, notice period, renewal term, termination notice period, liability cap.
  3. Strict evidence lineage preservation: fact → source clause → chunk → page → contract.
  4. Database persistence using the contract_facts table with fact_key, fact_value, verbatim_evidence, confidence.
  5. Idempotency (second run returns existing records without calling LLM).
  6. Force re-extraction (clears previous facts and runs fresh extraction).
  7. Graceful handling of missing, malformed, or invalid LLM output via Phase 6A validation.
  8. Error cases: Contract not found (404), No clauses found (400).
  9. Listing and filtering by fact_key.
 10. REST API endpoints (POST /extract-facts and GET /facts, with /api/v1 aliases).
 11. 100% mocked LLM calls: zero real API calls, zero secrets or tokens required.
"""

from unittest.mock import AsyncMock, MagicMock
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.schemas.contract_fact import (
    ClauseFactExtractionResult,
    ExtractedFactLLM,
    FactKey,
)
from app.services.contract_fact_service import (
    ContractNotFoundError,
    NoClausesFoundError,
    extract_contract_facts,
    extract_facts_from_clause,
    list_contract_facts,
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
        title="Phase 6D Test Master Services Agreement",
        vendor="Cyberdyne Systems",
        contract_type="MSA",
        status="active",
        processing_status="processing",
    )
    db_session.add(contract)
    db_session.commit()

    try:
        yield contract
    finally:
        # Cascade cleanup: facts, clauses, chunks, contract
        db_session.query(ContractFact).filter(ContractFact.contract_id == contract.id).delete()
        db_session.query(Clause).filter(Clause.contract_id == contract.id).delete()
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract.id).delete()
        db_session.query(Contract).filter(Contract.id == contract.id).delete()
        db_session.commit()


@pytest.fixture
def test_clauses(db_session: Session, test_contract: Contract):
    """Creates 2 ordered DocumentChunks and Clauses for the test contract."""
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        chunk_index=0,
        page_number=1,
        section_header="Section 1 — Parties and Term",
        char_start=0,
        char_end=280,
        text=(
            "This Master Services Agreement is entered into on January 1, 2025 ('Effective Date') "
            "between Cyberdyne Systems ('Vendor') and Acme Enterprise Corp ('Customer'). "
            "The initial term shall expire on December 31, 2027, with automatic 1-year renewal terms "
            "unless either party provides 60 days written notice prior to expiration."
        ),
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        chunk_index=1,
        page_number=2,
        section_header="Section 14 — Governing Law and Dispute Resolution",
        char_start=281,
        char_end=580,
        text=(
            "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, "
            "without regard to choice of law principles. Any dispute arising under this Agreement shall be resolved "
            "exclusively in the state or federal courts located in Wilmington, Delaware."
        ),
    )
    db_session.add(chunk1)
    db_session.add(chunk2)
    db_session.flush()

    clause1 = Clause(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        source_chunk_id=chunk1.id,
        clause_type="auto_renewal",
        clause_label="Section 1.2 — Term and Renewal",
        verbatim_text=(
            "This Master Services Agreement is entered into on January 1, 2025 ('Effective Date') "
            "between Cyberdyne Systems ('Vendor') and Acme Enterprise Corp ('Customer'). "
            "The initial term shall expire on December 31, 2027, with automatic 1-year renewal terms "
            "unless either party provides 60 days written notice prior to expiration."
        ),
        page_number=1,
    )
    clause2 = Clause(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        source_chunk_id=chunk2.id,
        clause_type="governing_law",
        clause_label="Section 14.1 — Governing Law & Jurisdiction",
        verbatim_text=(
            "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware. "
            "Any dispute shall be resolved in the state or federal courts located in Wilmington, Delaware."
        ),
        page_number=2,
    )
    db_session.add(clause1)
    db_session.add(clause2)
    db_session.commit()

    return [clause1, clause2]


# ====================================================================
# 1. Clause-Level Fact Extraction Unit Tests
# ====================================================================

class TestClauseFactExtraction:
    """Unit tests for extract_facts_from_clause."""

    @pytest.mark.asyncio
    async def test_extract_facts_from_clause_success(self):
        """Extracts valid facts from a clause using a mocked provider."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseFactExtractionResult(
                facts=[
                    ExtractedFactLLM(
                        fact_key=FactKey.EFFECTIVE_DATE,
                        fact_value="2025-01-01",
                        verbatim_evidence="entered into on January 1, 2025 ('Effective Date')",
                        confidence=0.99,
                    ),
                    ExtractedFactLLM(
                        fact_key=FactKey.PARTIES,
                        fact_value="Cyberdyne Systems and Acme Enterprise Corp",
                        fact_value_json='["Cyberdyne Systems", "Acme Enterprise Corp"]',
                        verbatim_evidence="between Cyberdyne Systems ('Vendor') and Acme Enterprise Corp ('Customer')",
                        confidence=0.98,
                    ),
                    ExtractedFactLLM(
                        fact_key=FactKey.NOTICE_PERIOD,
                        fact_value="60 days",
                        verbatim_evidence="unless either party provides 60 days written notice",
                        confidence=0.95,
                    ),
                ],
                has_facts=True,
            )
        )

        clause = Clause(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            source_chunk_id=uuid.uuid4(),
            clause_type="auto_renewal",
            clause_label="Section 1",
            verbatim_text="Sample clause text",
            page_number=1,
        )

        facts = await extract_facts_from_clause(clause, mock_provider)
        assert len(facts) == 3
        assert facts[0].fact_key == FactKey.EFFECTIVE_DATE
        assert facts[0].fact_value == "2025-01-01"
        assert facts[1].fact_key == FactKey.PARTIES
        assert facts[1].fact_value == "Cyberdyne Systems and Acme Enterprise Corp"
        assert facts[2].fact_key == FactKey.NOTICE_PERIOD
        assert facts[2].fact_value == "60 days"

    @pytest.mark.asyncio
    async def test_extract_facts_from_clause_empty(self):
        """Returns empty list when clause contains no operative facts."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseFactExtractionResult(
                facts=[],
                has_facts=False,
            )
        )

        clause = Clause(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            clause_type="boilerplate",
            verbatim_text="The headings in this Agreement are for reference only.",
            page_number=5,
        )

        facts = await extract_facts_from_clause(clause, mock_provider)
        assert facts == []

    @pytest.mark.asyncio
    async def test_extract_facts_gracefully_handles_structured_output_error(self):
        """Handles StructuredOutputParseError gracefully by logging and returning empty list."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            side_effect=StructuredOutputParseError("Malformed JSON from LLM")
        )

        clause = Clause(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            clause_type="payment",
            verbatim_text="Some text",
            page_number=1,
        )

        facts = await extract_facts_from_clause(clause, mock_provider)
        assert facts == []


# ====================================================================
# 2. Contract Fact Extraction Service Tests (Database Verified)
# ====================================================================

class TestContractFactExtractionService:
    """Service-level tests verifying database persistence, lineage, idempotency, and re-extraction."""

    @pytest.mark.asyncio
    async def test_extract_and_persist_contract_facts(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Extracts facts from clauses, persists them, and verifies lineage and metrics."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)

        async def mock_generate(prompt, schema, **kwargs):
            if "Term and Renewal" in prompt:
                return ClauseFactExtractionResult(
                    facts=[
                        ExtractedFactLLM(
                            fact_key=FactKey.EFFECTIVE_DATE,
                            fact_value="2025-01-01",
                            verbatim_evidence="entered into on January 1, 2025",
                            confidence=0.99,
                        ),
                        ExtractedFactLLM(
                            fact_key=FactKey.EXPIRATION_DATE,
                            fact_value="2027-12-31",
                            verbatim_evidence="expire on December 31, 2027",
                            confidence=0.98,
                        ),
                        ExtractedFactLLM(
                            fact_key=FactKey.NOTICE_PERIOD,
                            fact_value="60 days",
                            verbatim_evidence="60 days written notice prior to expiration",
                            confidence=0.95,
                        ),
                    ],
                    has_facts=True,
                )
            else:
                return ClauseFactExtractionResult(
                    facts=[
                        ExtractedFactLLM(
                            fact_key=FactKey.GOVERNING_LAW,
                            fact_value="State of Delaware",
                            verbatim_evidence="governed by and construed in accordance with the laws of the State of Delaware",
                            confidence=0.97,
                        ),
                        ExtractedFactLLM(
                            fact_key=FactKey.DISPUTE_FORUM,
                            fact_value="Wilmington, Delaware",
                            verbatim_evidence="courts located in Wilmington, Delaware",
                            confidence=0.94,
                        ),
                    ],
                    has_facts=True,
                )

        mock_provider.generate_structured = AsyncMock(side_effect=mock_generate)

        response = await extract_contract_facts(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )

        assert response.contract_id == test_contract.id
        assert response.total_clauses_analyzed == 2
        assert response.total_facts_extracted == 5
        assert response.facts_by_key == {
            "effective_date": 1,
            "expiration_date": 1,
            "notice_period": 1,
            "governing_law": 1,
            "dispute_forum": 1,
        }
        assert len(response.facts) == 5

        # Verify strict lineage: fact → source clause → chunk → page → contract
        eff_fact = next(f for f in response.facts if f.fact_key == "effective_date")
        assert eff_fact.contract_id == test_contract.id
        assert eff_fact.source_clause_id == test_clauses[0].id
        assert eff_fact.source_chunk_id == test_clauses[0].source_chunk_id
        assert eff_fact.page_number == 1
        assert eff_fact.fact_value == "2025-01-01"

        gov_fact = next(f for f in response.facts if f.fact_key == "governing_law")
        assert gov_fact.contract_id == test_contract.id
        assert gov_fact.source_clause_id == test_clauses[1].id
        assert gov_fact.source_chunk_id == test_clauses[1].source_chunk_id
        assert gov_fact.page_number == 2
        assert gov_fact.fact_value == "State of Delaware"

        # Verify database persistence
        db_facts = db_session.query(ContractFact).filter(ContractFact.contract_id == test_contract.id).all()
        assert len(db_facts) == 5

    @pytest.mark.asyncio
    async def test_extraction_idempotency(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Second call with force_reextract=False returns existing records without re-calling LLM."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseFactExtractionResult(
                facts=[
                    ExtractedFactLLM(
                        fact_key=FactKey.GOVERNING_LAW,
                        fact_value="Delaware",
                        verbatim_evidence="laws of Delaware",
                    )
                ],
                has_facts=True,
            )
        )

        # First run
        res1 = await extract_contract_facts(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )
        assert res1.total_facts_extracted > 0
        call_count_1 = mock_provider.generate_structured.call_count

        # Second run: should return existing without re-calling LLM
        res2 = await extract_contract_facts(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )

        assert res2.total_facts_extracted == res1.total_facts_extracted
        assert mock_provider.generate_structured.call_count == call_count_1

    @pytest.mark.asyncio
    async def test_force_reextract_replaces_facts(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Calling with force_reextract=True clears existing facts and extracts fresh ones."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseFactExtractionResult(
                facts=[
                    ExtractedFactLLM(
                        fact_key=FactKey.CURRENCY,
                        fact_value="USD",
                        verbatim_evidence="payable in USD",
                    )
                ],
                has_facts=True,
            )
        )

        # First run
        await extract_contract_facts(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )
        call_count_1 = mock_provider.generate_structured.call_count

        # Second run with force_reextract=True
        res = await extract_contract_facts(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=True,
            provider=mock_provider,
        )

        assert mock_provider.generate_structured.call_count > call_count_1
        assert res.total_facts_extracted > 0
        assert all(f.fact_key == "currency" for f in res.facts)

    @pytest.mark.asyncio
    async def test_contract_not_found_raises_error(self, db_session: Session):
        """Raises ContractNotFoundError for non-existent contract ID."""
        random_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError) as exc_info:
            await extract_contract_facts(db=db_session, contract_id=random_id)
        assert str(random_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_clauses_found_raises_error(
        self, db_session: Session, test_contract: Contract
    ):
        """Raises NoClausesFoundError if contract has no clauses."""
        with pytest.raises(NoClausesFoundError) as exc_info:
            await extract_contract_facts(db=db_session, contract_id=test_contract.id)
        assert "no extracted clauses" in str(exc_info.value).lower()

    def test_list_contract_facts_and_filtering(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Tests list_contract_facts with fact_key filtering."""
        # Seed 2 facts manually
        f1 = ContractFact(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            source_clause_id=test_clauses[0].id,
            source_chunk_id=test_clauses[0].source_chunk_id,
            page_number=1,
            fact_key="effective_date",
            fact_value="2025-01-01",
            verbatim_evidence="Effective Date: January 1, 2025",
        )
        f2 = ContractFact(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            source_clause_id=test_clauses[1].id,
            source_chunk_id=test_clauses[1].source_chunk_id,
            page_number=2,
            fact_key="governing_law",
            fact_value="Delaware",
            verbatim_evidence="governed by laws of Delaware",
        )
        db_session.add(f1)
        db_session.add(f2)
        db_session.commit()

        # Unfiltered list
        all_res = list_contract_facts(db=db_session, contract_id=test_contract.id)
        assert all_res.total_facts == 2

        # Filter by fact_key="effective_date"
        eff_res = list_contract_facts(
            db=db_session, contract_id=test_contract.id, fact_key="effective_date"
        )
        assert eff_res.total_facts == 1
        assert eff_res.facts[0].fact_key == "effective_date"
        assert eff_res.facts[0].fact_value == "2025-01-01"

        # Filter by fact_key="governing_law"
        gov_res = list_contract_facts(
            db=db_session, contract_id=test_contract.id, fact_key="governing_law"
        )
        assert gov_res.total_facts == 1
        assert gov_res.facts[0].fact_key == "governing_law"
        assert gov_res.facts[0].fact_value == "Delaware"

        # Filter by non-existent key
        none_res = list_contract_facts(
            db=db_session, contract_id=test_contract.id, fact_key="liability_cap"
        )
        assert none_res.total_facts == 0


# ====================================================================
# 3. REST API Endpoint Tests
# ====================================================================

class TestContractFactExtractionAPI:
    """Integration tests verifying HTTP endpoints."""

    def test_api_contract_not_found(self, test_client: TestClient):
        """POST /contracts/{random_id}/extract-facts returns 404."""
        random_id = uuid.uuid4()
        response = test_client.post(f"/contracts/{random_id}/extract-facts")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_api_no_clauses_returns_400(
        self, test_client: TestClient, test_contract: Contract
    ):
        """POST /contracts/{id}/extract-facts returns 400 if no clauses exist."""
        response = test_client.post(f"/contracts/{test_contract.id}/extract-facts")
        assert response.status_code == 400
        assert "no extracted clauses" in response.json()["detail"].lower()

    def test_api_get_facts_empty_initially(
        self, test_client: TestClient, test_contract: Contract
    ):
        """GET /contracts/{id}/facts returns empty list when no facts exist."""
        response = test_client.get(f"/contracts/{test_contract.id}/facts")
        assert response.status_code == 200
        data = response.json()
        assert data["contract_id"] == str(test_contract.id)
        assert data["total_facts"] == 0
        assert data["facts"] == []

    def test_api_get_facts_versioned_alias(
        self, test_client: TestClient, test_contract: Contract
    ):
        """GET /api/v1/contracts/{id}/facts behaves identically to /contracts/{id}/facts."""
        response = test_client.get(f"/api/v1/contracts/{test_contract.id}/facts")
        assert response.status_code == 200
        assert response.json()["total_facts"] == 0
