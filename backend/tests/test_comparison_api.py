"""
ContractIQ — Tests for Cross-Contract Comparison API (Phase 11A–11E)

Verifies:
  - 11A: Strongly typed comparison schemas and service foundation.
  - 11B: Structured cross-contract comparison (2 contracts, multi-contract 3+ contracts).
         Handles dates, values, notice periods, liability caps, governing law, and obligations.
  - 11C: Evidence-backed comparison with 6-tier lineage:
         comparison -> fact/obligation/clause -> chunk -> page -> contract.
         Detects and flags wrong-contract evidence lineage.
  - 11D: Deterministic difference analysis without LLM calls (numeric variances, notice differences,
         missing term identification).
  - 11E: Scoping validation, duplicate contract ID rejection, missing contracts, missing facts,
         and REST endpoint registration.
  - Zero real LLM or external API calls (100% deterministic).
"""

from datetime import date
from typing import Any, Optional
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.schemas.comparison import (
    ContractComparisonRequest,
    DifferenceSeverity,
    DifferenceType,
)
from app.schemas.rag import CitationVerificationStatus
from app.services.comparison_service import (
    ComparisonScopingError,
    compare_contracts_structured,
)


@pytest.fixture
def db_session():
    """Database session fixture."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def comparison_contracts_setup(db_session: Session):
    """
    Sets up 3 test contracts with chunks, structured ContractFacts, and obligations.
    - Contract 1: Apex Cloud (SaaS, $120,000, 30-day notice, New York law, capped liability)
    - Contract 2: Beta Data (DPA, $240,000, 60-day notice, California law, uncapped liability)
    - Contract 3: Gamma Hosting (Hosting, missing notice period, Delaware law, $50,000)
    """
    # ----------------------------------------------------------------
    # Contract 1: Apex Cloud
    # ----------------------------------------------------------------
    c1_id = uuid.uuid4()
    c1 = Contract(
        id=c1_id,
        title="Apex Cloud Master Services Agreement",
        vendor="Apex Cloud Inc",
        contract_type="SaaS",
        status="active",
        effective_date=date(2025, 1, 1),
        expiry_date=date(2026, 1, 1),
        contract_value=120000.0,
        currency="USD",
        has_auto_renewal=True,
        page_count=12,
        processing_status="completed",
    )
    db_session.add(c1)

    chunk_c1 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=c1_id,
        chunk_index=0,
        page_number=3,
        section_header="Section 6. Term & Termination",
        text="Either party may terminate upon thirty (30) days prior written notice.",
        char_start=0,
        char_end=74,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk_c1)

    fact_c1_notice = ContractFact(
        id=uuid.uuid4(),
        contract_id=c1_id,
        source_chunk_id=chunk_c1.id,
        fact_key="notice_period",
        fact_value="30 days",
        verbatim_evidence="Either party may terminate upon thirty (30) days prior written notice.",
        page_number=3,
    )
    db_session.add(fact_c1_notice)

    fact_c1_val = ContractFact(
        id=uuid.uuid4(),
        contract_id=c1_id,
        source_chunk_id=chunk_c1.id,
        fact_key="contract_value",
        fact_value="$120,000",
        verbatim_evidence="Total contract price is $120,000 annually.",
        page_number=3,
    )
    db_session.add(fact_c1_val)

    fact_c1_law = ContractFact(
        id=uuid.uuid4(),
        contract_id=c1_id,
        source_chunk_id=chunk_c1.id,
        fact_key="governing_law",
        fact_value="State of New York",
        verbatim_evidence="Governed by the laws of the State of New York.",
        page_number=10,
    )
    db_session.add(fact_c1_law)

    ob_c1 = Obligation(
        id=uuid.uuid4(),
        contract_id=c1_id,
        source_chunk_id=chunk_c1.id,
        title="Deliver Annual SOC2 Report",
        description="Vendor must deliver annual SOC2 report to customer.",
        responsible_party="Vendor",
        priority="high",
        due_date=date(2025, 6, 30),
        page_number=5,
    )
    db_session.add(ob_c1)

    # ----------------------------------------------------------------
    # Contract 2: Beta Data
    # ----------------------------------------------------------------
    c2_id = uuid.uuid4()
    c2 = Contract(
        id=c2_id,
        title="Beta Data Processing Agreement",
        vendor="Beta Analytics LLC",
        contract_type="DPA",
        status="active",
        effective_date=date(2025, 3, 1),
        expiry_date=date(2026, 3, 1),
        contract_value=240000.0,
        currency="USD",
        has_auto_renewal=False,
        page_count=8,
        processing_status="completed",
    )
    db_session.add(c2)

    chunk_c2 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=c2_id,
        chunk_index=0,
        page_number=5,
        section_header="Section 9. Termination Notice",
        text="Customer may terminate upon sixty (60) days advance notice.",
        char_start=0,
        char_end=60,
        embedding=[0.1] * 768,
    )
    db_session.add(chunk_c2)

    fact_c2_notice = ContractFact(
        id=uuid.uuid4(),
        contract_id=c2_id,
        source_chunk_id=chunk_c2.id,
        fact_key="notice_period",
        fact_value="60 days",
        verbatim_evidence="Customer may terminate upon sixty (60) days advance notice.",
        page_number=5,
    )
    db_session.add(fact_c2_notice)

    fact_c2_val = ContractFact(
        id=uuid.uuid4(),
        contract_id=c2_id,
        source_chunk_id=chunk_c2.id,
        fact_key="contract_value",
        fact_value="$240,000",
        verbatim_evidence="Annual processing fee is $240,000.",
        page_number=2,
    )
    db_session.add(fact_c2_val)

    fact_c2_law = ContractFact(
        id=uuid.uuid4(),
        contract_id=c2_id,
        source_chunk_id=chunk_c2.id,
        fact_key="governing_law",
        fact_value="State of California",
        verbatim_evidence="Governed by the laws of California.",
        page_number=7,
    )
    db_session.add(fact_c2_law)

    # ----------------------------------------------------------------
    # Contract 3: Gamma Hosting (Missing notice period)
    # ----------------------------------------------------------------
    c3_id = uuid.uuid4()
    c3 = Contract(
        id=c3_id,
        title="Gamma Hosting Service Order",
        vendor="Gamma Hosting Inc",
        contract_type="Hosting",
        status="active",
        effective_date=date(2025, 2, 1),
        expiry_date=date(2026, 2, 1),
        contract_value=50000.0,
        currency="USD",
        has_auto_renewal=True,
        page_count=4,
        processing_status="completed",
    )
    db_session.add(c3)

    fact_c3_val = ContractFact(
        id=uuid.uuid4(),
        contract_id=c3_id,
        fact_key="contract_value",
        fact_value="$50,000",
        verbatim_evidence="Total contract commitment $50,000.",
        page_number=1,
    )
    db_session.add(fact_c3_val)

    fact_c3_law = ContractFact(
        id=uuid.uuid4(),
        contract_id=c3_id,
        fact_key="governing_law",
        fact_value="State of Delaware",
        verbatim_evidence="Governed by Delaware law.",
        page_number=4,
    )
    db_session.add(fact_c3_law)

    db_session.commit()

    data = {
        "c1": c1,
        "chunk_c1": chunk_c1,
        "c2": c2,
        "chunk_c2": chunk_c2,
        "c3": c3,
    }

    yield data

    # Cleanup
    db_session.query(Obligation).filter(Obligation.contract_id.in_([c1_id, c2_id, c3_id])).delete()
    db_session.query(ContractFact).filter(ContractFact.contract_id.in_([c1_id, c2_id, c3_id])).delete()
    db_session.query(DocumentChunk).filter(DocumentChunk.contract_id.in_([c1_id, c2_id, c3_id])).delete()
    db_session.query(Contract).filter(Contract.id.in_([c1_id, c2_id, c3_id])).delete()
    db_session.commit()


# ====================================================================
# Unit & Integration Tests (11A–11E)
# ====================================================================

class TestContractComparison:
    """Test suite for Cross-Contract Comparison Engine."""

    def test_successful_two_contract_comparison(
        self, db_session: Session, comparison_contracts_setup: dict
    ):
        """11B & 11D: Compares 2 contracts, tests numeric variance and evidence lineage."""
        c1 = comparison_contracts_setup["c1"]
        c2 = comparison_contracts_setup["c2"]

        req = ContractComparisonRequest(
            contract_ids=[c1.id, c2.id],
            field_keys=["contract_value", "notice_period", "governing_law"],
            include_obligations=True,
        )

        resp = compare_contracts_structured(db=db_session, request=req)

        assert resp.total_contracts == 2
        assert len(resp.contract_headers) == 2
        assert resp.contract_headers[0].title == c1.title
        assert resp.contract_headers[1].title == c2.title

        # Check fields
        assert len(resp.fields_compared) == 3
        val_row = next(r for r in resp.fields_compared if r.field_key == "contract_value")
        assert val_row.has_variance is True
        assert val_row.deterministic_difference is not None
        assert val_row.deterministic_difference.difference_type == DifferenceType.NUMERIC_COMPARISON
        assert val_row.deterministic_difference.highest_contract_id == c2.id
        assert val_row.deterministic_difference.lowest_contract_id == c1.id

        # 11C: Evidence check
        val_c1 = val_row.values_by_contract[str(c1.id)]
        assert val_c1.is_available is True
        assert val_c1.value == "$120,000"
        assert val_c1.numeric_value == 120000.0
        assert val_c1.evidence is not None
        assert val_c1.evidence.contract_id == c1.id
        assert val_c1.evidence.verification_status == CitationVerificationStatus.VALID
        assert val_c1.evidence.page_number == 3

        # Notice period difference
        notice_row = next(r for r in resp.fields_compared if r.field_key == "notice_period")
        assert notice_row.has_variance is True
        assert notice_row.deterministic_difference.difference_type == DifferenceType.TIMEFRAME_DIFFERENCE
        assert "Variance of 30.0 days" in notice_row.deterministic_difference.summary

        # Obligations check
        assert len(resp.obligations) == 1
        assert resp.obligations[0].contract_id == c1.id
        assert resp.obligations[0].title == "Deliver Annual SOC2 Report"
        assert resp.obligations[0].evidence.verification_status == CitationVerificationStatus.VALID

    def test_multi_contract_three_way_comparison(
        self, db_session: Session, comparison_contracts_setup: dict
    ):
        """11B: Multi-contract comparison across 3 contracts with missing fields."""
        c1 = comparison_contracts_setup["c1"]
        c2 = comparison_contracts_setup["c2"]
        c3 = comparison_contracts_setup["c3"]

        req = ContractComparisonRequest(
            contract_ids=[c1.id, c2.id, c3.id],
            field_keys=["contract_value", "notice_period", "governing_law"],
        )

        resp = compare_contracts_structured(db=db_session, request=req)

        assert resp.total_contracts == 3
        assert len(resp.contract_headers) == 3

        # Notice period is missing in c3
        notice_row = next(r for r in resp.fields_compared if r.field_key == "notice_period")
        assert notice_row.has_variance is True
        assert c3.id in notice_row.missing_in_contracts
        assert notice_row.deterministic_difference.difference_type == DifferenceType.MISSING_TERM
        assert c3.title in notice_row.deterministic_difference.summary

        # Missing data summary
        assert resp.missing_data_summary[str(c3.id)] >= 1

    def test_missing_contract_raises_scoping_error(
        self, db_session: Session, comparison_contracts_setup: dict
    ):
        """11E: Enforces scoping: nonexistent contract ID raises ComparisonScopingError."""
        c1 = comparison_contracts_setup["c1"]
        fake_id = uuid.uuid4()

        req = ContractComparisonRequest(
            contract_ids=[c1.id, fake_id],
        )

        with pytest.raises(ComparisonScopingError) as exc_info:
            compare_contracts_structured(db=db_session, request=req)
        assert "do not exist or are inaccessible" in str(exc_info.value)

    def test_duplicate_contract_ids_rejected_by_schema(
        self, comparison_contracts_setup: dict
    ):
        """11E: Duplicate contract IDs raise validation error."""
        c1 = comparison_contracts_setup["c1"]

        with pytest.raises(ValueError) as exc_info:
            ContractComparisonRequest(
                contract_ids=[c1.id, c1.id],
            )
        assert "Duplicate contract IDs are not allowed" in str(exc_info.value)

    def test_wrong_contract_evidence_lineage_flagged(
        self, db_session: Session, comparison_contracts_setup: dict
    ):
        """11C: If a contract fact references a chunk belonging to another contract, flag WRONG_CONTRACT."""
        c1 = comparison_contracts_setup["c1"]
        c2 = comparison_contracts_setup["c2"]
        chunk_c2 = comparison_contracts_setup["chunk_c2"]

        # Create a corrupted fact on c1 referencing chunk on c2
        corrupted_fact = ContractFact(
            id=uuid.uuid4(),
            contract_id=c1.id,
            source_chunk_id=chunk_c2.id,  # Points to c2's chunk!
            fact_key="dispute_forum",
            fact_value="Corrupted Venue",
            verbatim_evidence="Corrupted quote",
            page_number=5,
        )
        db_session.add(corrupted_fact)
        db_session.commit()

        try:
            req = ContractComparisonRequest(
                contract_ids=[c1.id, c2.id],
                field_keys=["dispute_forum"],
            )
            resp = compare_contracts_structured(db=db_session, request=req)

            row = resp.fields_compared[0]
            val_c1 = row.values_by_contract[str(c1.id)]
            assert val_c1.evidence is not None
            assert val_c1.evidence.verification_status == CitationVerificationStatus.WRONG_CONTRACT
            assert "Wrong contract" in val_c1.evidence.verification_notes
        finally:
            db_session.delete(corrupted_fact)
            db_session.commit()

    def test_empty_contract_handles_gracefully(
        self, db_session: Session, comparison_contracts_setup: dict
    ):
        """11B & 11E: Compares with an empty contract having zero facts/chunks."""
        c1 = comparison_contracts_setup["c1"]

        empty_id = uuid.uuid4()
        empty_c = Contract(
            id=empty_id,
            title="Empty Draft Contract",
            status="active",
            processing_status="completed",
        )
        db_session.add(empty_c)
        db_session.commit()

        try:
            req = ContractComparisonRequest(
                contract_ids=[c1.id, empty_id],
                field_keys=["notice_period"],
            )
            resp = compare_contracts_structured(db=db_session, request=req)

            assert resp.total_contracts == 2
            row = resp.fields_compared[0]
            assert row.values_by_contract[str(empty_id)].is_available is False
            assert row.values_by_contract[str(empty_id)].value is None
            assert empty_id in row.missing_in_contracts
        finally:
            db_session.delete(empty_c)
            db_session.commit()


# ====================================================================
# REST API Endpoint Tests via TestClient
# ====================================================================

def test_comparison_api_endpoints_mounted(comparison_contracts_setup: dict):
    """11E: Verifies POST and GET /contracts/compare endpoints are mounted and work."""
    client = TestClient(app)
    c1 = comparison_contracts_setup["c1"]
    c2 = comparison_contracts_setup["c2"]

    # 1. POST /contracts/compare
    resp = client.post(
        "/contracts/compare",
        json={
            "contract_ids": [str(c1.id), str(c2.id)],
            "field_keys": ["contract_value", "notice_period"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_contracts"] == 2
    assert len(data["fields_compared"]) == 2

    # 2. GET /contracts/compare?contract_id=...&contract_id=...
    resp_get = client.get(
        f"/contracts/compare?contract_id={c1.id}&contract_id={c2.id}"
    )
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["total_contracts"] == 2

    # 3. GET with versioned /api/v1 prefix
    resp_v1 = client.post(
        "/api/v1/contracts/compare",
        json={
            "contract_ids": [str(c1.id), str(c2.id)],
            "field_keys": ["governing_law"],
        },
    )
    assert resp_v1.status_code == 200

    # 4. Unknown contract returns 404
    fake_id = uuid.uuid4()
    resp_404 = client.post(
        "/contracts/compare",
        json={
            "contract_ids": [str(c1.id), str(fake_id)],
        },
    )
    assert resp_404.status_code == 404

    # 5. Single contract fails validation (< 2 contracts)
    resp_422 = client.post(
        "/contracts/compare",
        json={
            "contract_ids": [str(c1.id)],
        },
    )
    assert resp_422.status_code == 422
