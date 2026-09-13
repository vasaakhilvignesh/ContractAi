"""
ContractIQ — Tests for Obligation Extraction (Phase 6C)

Verifies:
  1. Pydantic schemas for extracted obligations (ObligationType, ExtractedObligationLLM, ClauseObligationExtractionResult).
  2. Extraction of obligation description, responsible party, obligation type, deadline/timing, frequency, verbatim text.
  3. Strict evidence lineage preservation: obligation → clause → chunk → page → contract.
  4. Database persistence using the obligations table with obligation_type, deadline_info, and extraction_confidence.
  5. Idempotency (second run returns existing records without calling LLM).
  6. Force re-extraction (clears previous obligations and runs fresh extraction).
  7. Graceful handling of missing, malformed, or invalid LLM output via Phase 6A validation.
  8. Error cases: Contract not found (404), No clauses found (400).
  9. Listing and filtering by party, obligation_type, and status.
 10. REST API endpoints (POST /extract-obligations and GET /obligations, with /api/v1 aliases).
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
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.schemas.obligation import (
    ClauseObligationExtractionResult,
    ExtractedObligationLLM,
    ObligationType,
)
from app.services.obligation_extraction_service import (
    ContractNotFoundError,
    NoClausesFoundError,
    extract_contract_obligations,
    extract_obligations_from_clause,
    list_contract_obligations,
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
        title="Phase 6C Test MSA Contract",
        vendor="Apex Cloud Systems",
        contract_type="MSA",
        status="active",
        processing_status="processing",
    )
    db_session.add(contract)
    db_session.commit()

    try:
        yield contract
    finally:
        # Cascade cleanup: obligations, clauses, chunks, contract
        db_session.query(Obligation).filter(Obligation.contract_id == contract.id).delete()
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
        section_header="Section 4 — Fees and Payment Terms",
        char_start=0,
        char_end=250,
        text="Customer shall pay all undisputed invoices within thirty (30) days of receipt.",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        chunk_index=1,
        page_number=2,
        section_header="Section 9 — Security and Compliance",
        char_start=251,
        char_end=550,
        text="Vendor shall provide quarterly SOC 2 compliance reports and maintain SOC 2 Type II certification.",
    )
    db_session.add(chunk1)
    db_session.add(chunk2)
    db_session.flush()

    clause1 = Clause(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        source_chunk_id=chunk1.id,
        clause_type="payment",
        clause_label="Section 4.1 — Invoice Payment",
        verbatim_text="Customer shall pay all undisputed invoices within thirty (30) days of receipt.",
        page_number=1,
    )
    clause2 = Clause(
        id=uuid.uuid4(),
        contract_id=test_contract.id,
        source_chunk_id=chunk2.id,
        clause_type="compliance",
        clause_label="Section 9.3 — Security Audit Reporting",
        verbatim_text="Vendor shall provide quarterly SOC 2 compliance reports and maintain SOC 2 Type II certification.",
        page_number=2,
    )
    db_session.add(clause1)
    db_session.add(clause2)
    db_session.commit()

    return [clause1, clause2]


# ====================================================================
# 1. Clause-Level Extraction Unit Tests
# ====================================================================

class TestClauseObligationExtraction:
    """Unit tests for extract_obligations_from_clause."""

    @pytest.mark.asyncio
    async def test_extract_obligations_from_clause_success(self):
        """Extracts valid obligations from a clause using a mocked provider."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseObligationExtractionResult(
                obligations=[
                    ExtractedObligationLLM(
                        title="Pay Invoices within 30 Days",
                        description="Customer must pay undisputed invoices within 30 days of receipt.",
                        responsible_party="Customer",
                        obligation_type=ObligationType.PAYMENT,
                        due_date_description="Within 30 days of receipt",
                        frequency="Per invoice",
                        is_recurring=False,
                        verbatim_evidence="Customer shall pay all undisputed invoices within thirty (30) days of receipt.",
                        confidence=0.97,
                    )
                ],
                has_obligations=True,
            )
        )

        clause = Clause(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            source_chunk_id=uuid.uuid4(),
            clause_type="payment",
            clause_label="Section 4.1",
            verbatim_text="Customer shall pay all invoices within 30 days.",
            page_number=1,
        )

        obligations = await extract_obligations_from_clause(clause, mock_provider)
        assert len(obligations) == 1
        assert obligations[0].title == "Pay Invoices within 30 Days"
        assert obligations[0].responsible_party == "Customer"
        assert obligations[0].obligation_type == ObligationType.PAYMENT
        assert obligations[0].due_date_description == "Within 30 days of receipt"
        assert obligations[0].confidence == 0.97

    @pytest.mark.asyncio
    async def test_extract_obligations_from_clause_empty(self):
        """Returns empty list when clause contains no operative obligations."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseObligationExtractionResult(
                obligations=[],
                has_obligations=False,
            )
        )

        clause = Clause(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            clause_type="governing_law",
            verbatim_text="This Agreement shall be governed by the laws of California.",
            page_number=3,
        )

        obligations = await extract_obligations_from_clause(clause, mock_provider)
        assert obligations == []

    @pytest.mark.asyncio
    async def test_extract_obligations_gracefully_handles_structured_output_error(self):
        """Handles StructuredOutputParseError gracefully by logging and returning empty list."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            side_effect=StructuredOutputParseError("Malformed JSON from LLM")
        )

        clause = Clause(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            clause_type="payment",
            verbatim_text="Some clause text",
            page_number=1,
        )

        obligations = await extract_obligations_from_clause(clause, mock_provider)
        assert obligations == []


# ====================================================================
# 2. Contract Obligation Extraction Service Tests (Database Verified)
# ====================================================================

class TestContractObligationExtractionService:
    """Service-level tests verifying database persistence, lineage, idempotency, and re-extraction."""

    @pytest.mark.asyncio
    async def test_extract_and_persist_contract_obligations(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Extracts obligations from clauses, persists them, and verifies lineage and metrics."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)

        async def mock_generate(prompt, schema, **kwargs):
            if "Section 4" in prompt:
                return ClauseObligationExtractionResult(
                    obligations=[
                        ExtractedObligationLLM(
                            title="Pay Invoices within 30 Days",
                            description="Customer must pay undisputed invoices within 30 days of receipt.",
                            responsible_party="Customer",
                            obligation_type=ObligationType.PAYMENT,
                            due_date_description="Within 30 days of receipt",
                            frequency="Per invoice",
                            is_recurring=False,
                            verbatim_evidence="Customer shall pay all undisputed invoices within thirty (30) days of receipt.",
                            confidence=0.98,
                        )
                    ],
                    has_obligations=True,
                )
            else:
                return ClauseObligationExtractionResult(
                    obligations=[
                        ExtractedObligationLLM(
                            title="Provide Quarterly SOC 2 Reports",
                            description="Vendor must supply SOC 2 Type II audit reports on a quarterly basis.",
                            responsible_party="Vendor",
                            obligation_type=ObligationType.REPORTING,
                            due_date_description="Quarterly",
                            frequency="Quarterly",
                            is_recurring=True,
                            verbatim_evidence="Vendor shall provide quarterly SOC 2 compliance reports.",
                            confidence=0.95,
                        )
                    ],
                    has_obligations=True,
                )

        mock_provider.generate_structured = AsyncMock(side_effect=mock_generate)

        response = await extract_contract_obligations(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )

        assert response.contract_id == test_contract.id
        assert response.total_clauses_analyzed == 2
        assert response.total_obligations_extracted == 2
        assert response.obligations_by_party == {"Customer": 1, "Vendor": 1}
        assert response.obligations_by_type == {"payment": 1, "reporting": 1}
        assert len(response.obligations) == 2

        # Verify strict lineage: obligation → clause → chunk → page → contract
        pay_ob = next(o for o in response.obligations if o.obligation_type == "payment")
        assert pay_ob.contract_id == test_contract.id
        assert pay_ob.source_clause_id == test_clauses[0].id
        assert pay_ob.source_chunk_id == test_clauses[0].source_chunk_id
        assert pay_ob.page_number == 1
        assert pay_ob.responsible_party == "Customer"
        assert pay_ob.deadline_info == "Within 30 days of receipt"
        assert pay_ob.status == "pending"

        rep_ob = next(o for o in response.obligations if o.obligation_type == "reporting")
        assert rep_ob.contract_id == test_contract.id
        assert rep_ob.source_clause_id == test_clauses[1].id
        assert rep_ob.source_chunk_id == test_clauses[1].source_chunk_id
        assert rep_ob.page_number == 2
        assert rep_ob.responsible_party == "Vendor"
        assert rep_ob.frequency == "Quarterly"
        assert rep_ob.is_recurring is True

        # Verify database persistence
        db_obs = db_session.query(Obligation).filter(Obligation.contract_id == test_contract.id).all()
        assert len(db_obs) == 2

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
            return_value=ClauseObligationExtractionResult(
                obligations=[
                    ExtractedObligationLLM(
                        title="Idempotent Obligation",
                        description="Test description",
                        responsible_party="Vendor",
                        obligation_type=ObligationType.DELIVERY,
                        verbatim_evidence="Vendor shall deliver items",
                    )
                ],
                has_obligations=True,
            )
        )

        # First run
        res1 = await extract_contract_obligations(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )
        assert res1.total_obligations_extracted > 0
        call_count_1 = mock_provider.generate_structured.call_count

        # Second run: should return existing without re-calling LLM
        res2 = await extract_contract_obligations(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )

        assert res2.total_obligations_extracted == res1.total_obligations_extracted
        assert mock_provider.generate_structured.call_count == call_count_1

    @pytest.mark.asyncio
    async def test_force_reextract_replaces_obligations(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Calling with force_reextract=True clears existing obligations and extracts fresh ones."""
        mock_provider = MagicMock(spec=StructuredLLMProvider)
        mock_provider.generate_structured = AsyncMock(
            return_value=ClauseObligationExtractionResult(
                obligations=[
                    ExtractedObligationLLM(
                        title="Re-extracted Obligation",
                        description="Fresh obligation description",
                        responsible_party="Customer",
                        obligation_type=ObligationType.CONFIDENTIALITY,
                        verbatim_evidence="Customer shall keep confidential",
                    )
                ],
                has_obligations=True,
            )
        )

        # First run
        await extract_contract_obligations(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=False,
            provider=mock_provider,
        )
        call_count_1 = mock_provider.generate_structured.call_count

        # Second run with force_reextract=True
        res = await extract_contract_obligations(
            db=db_session,
            contract_id=test_contract.id,
            force_reextract=True,
            provider=mock_provider,
        )

        assert mock_provider.generate_structured.call_count > call_count_1
        assert res.total_obligations_extracted > 0
        assert all(o.obligation_type == "confidentiality" for o in res.obligations)

    @pytest.mark.asyncio
    async def test_contract_not_found_raises_error(self, db_session: Session):
        """Raises ContractNotFoundError for non-existent contract ID."""
        random_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError) as exc_info:
            await extract_contract_obligations(db=db_session, contract_id=random_id)
        assert str(random_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_clauses_found_raises_error(
        self, db_session: Session, test_contract: Contract
    ):
        """Raises NoClausesFoundError if contract has no clauses."""
        with pytest.raises(NoClausesFoundError) as exc_info:
            await extract_contract_obligations(db=db_session, contract_id=test_contract.id)
        assert "no extracted clauses" in str(exc_info.value).lower()

    def test_list_contract_obligations_and_filtering(
        self,
        db_session: Session,
        test_contract: Contract,
        test_clauses: list[Clause],
    ):
        """Tests list_contract_obligations with party, obligation_type, and status filters."""
        # Seed 2 obligations manually
        ob1 = Obligation(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            source_clause_id=test_clauses[0].id,
            source_chunk_id=test_clauses[0].source_chunk_id,
            page_number=1,
            title="Pay Invoices",
            responsible_party="Customer",
            obligation_type="payment",
            deadline_info="30 days",
            status="pending",
        )
        ob2 = Obligation(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            source_clause_id=test_clauses[1].id,
            source_chunk_id=test_clauses[1].source_chunk_id,
            page_number=2,
            title="Deliver Reports",
            responsible_party="Vendor",
            obligation_type="reporting",
            deadline_info="Quarterly",
            status="completed",
        )
        db_session.add(ob1)
        db_session.add(ob2)
        db_session.commit()

        # Unfiltered list
        all_res = list_contract_obligations(db=db_session, contract_id=test_contract.id)
        assert all_res.total_obligations == 2

        # Filter by responsible_party="Customer"
        party_res = list_contract_obligations(
            db=db_session, contract_id=test_contract.id, responsible_party="Customer"
        )
        assert party_res.total_obligations == 1
        assert party_res.obligations[0].responsible_party == "Customer"

        # Filter by obligation_type="reporting"
        type_res = list_contract_obligations(
            db=db_session, contract_id=test_contract.id, obligation_type="reporting"
        )
        assert type_res.total_obligations == 1
        assert type_res.obligations[0].obligation_type == "reporting"

        # Filter by status="completed"
        status_res = list_contract_obligations(
            db=db_session, contract_id=test_contract.id, status="completed"
        )
        assert status_res.total_obligations == 1
        assert status_res.obligations[0].status == "completed"


# ====================================================================
# 3. REST API Endpoint Tests
# ====================================================================

class TestObligationExtractionAPI:
    """Integration tests verifying HTTP endpoints."""

    def test_api_contract_not_found(self, test_client: TestClient):
        """POST /contracts/{random_id}/extract-obligations returns 404."""
        random_id = uuid.uuid4()
        response = test_client.post(f"/contracts/{random_id}/extract-obligations")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_api_no_clauses_returns_400(
        self, test_client: TestClient, test_contract: Contract
    ):
        """POST /contracts/{id}/extract-obligations returns 400 if no clauses exist."""
        response = test_client.post(f"/contracts/{test_contract.id}/extract-obligations")
        assert response.status_code == 400
        assert "no extracted clauses" in response.json()["detail"].lower()

    def test_api_get_obligations_empty_initially(
        self, test_client: TestClient, test_contract: Contract
    ):
        """GET /contracts/{id}/obligations returns empty list when no obligations exist."""
        response = test_client.get(f"/contracts/{test_contract.id}/obligations")
        assert response.status_code == 200
        data = response.json()
        assert data["contract_id"] == str(test_contract.id)
        assert data["total_obligations"] == 0
        assert data["obligations"] == []

    def test_api_get_obligations_versioned_alias(
        self, test_client: TestClient, test_contract: Contract
    ):
        """GET /api/v1/contracts/{id}/obligations behaves identically to /contracts/{id}/obligations."""
        response = test_client.get(f"/api/v1/contracts/{test_contract.id}/obligations")
        assert response.status_code == 200
        assert response.json()["total_obligations"] == 0
