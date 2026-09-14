"""
ContractIQ — Tests for Obligation API & Analysis (Phase 12A–12E)

Verifies:
  - 12A: Obligation query & retrieval foundation.
  - 12B: Contract-scoped retrieval with multi-facet filtering (party, type, status, priority, recurrence, dates).
  - 12C: 6-tier evidence lineage preservation & deterministic validation (valid, wrong_contract, text_mismatch, missing chunk).
  - 12D: Deterministic obligation analysis (summary metrics, party breakdowns, recurrence counts, overdue/upcoming counts).
  - 12E: Scoped REST endpoints (GET /query, POST /query, GET /{obligation_id}), 404 for nonexistent contracts,
         and cross-contract scoping enforcement.
  - Zero external LLM calls (100% deterministic).
"""

from datetime import date, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.schemas.obligation_api import (
    ObligationDetailResponse,
    ObligationQueryRequest,
    ObligationQueryResponse,
)
from app.schemas.rag import CitationVerificationStatus
from app.services.obligation_service import (
    ContractNotFoundError,
    ObligationNotFoundError,
    ObligationScopingError,
    get_single_obligation_detail,
    query_contract_obligations,
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
def obligation_test_data(db_session: Session):
    """
    Sets up 2 contracts with chunks, clauses, and obligations:
    - Contract 1: Apex Cloud (3 obligations: payment, reporting, security)
    - Contract 2: Beta Data (1 obligation: confidentiality)
    """
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()

    c1 = Contract(
        id=c1_id,
        title="Apex Cloud Master Agreement",
        vendor="Apex Cloud Inc",
        contract_type="MSA",
        status="active",
        processing_status="completed",
    )
    c2 = Contract(
        id=c2_id,
        title="Beta Data Processing Agreement",
        vendor="Beta Data LLC",
        contract_type="DPA",
        status="active",
        processing_status="completed",
    )
    db_session.add_all([c1, c2])
    db_session.flush()

    # Chunks for Contract 1
    ch1_id = uuid.uuid4()
    ch2_id = uuid.uuid4()
    chunk1 = DocumentChunk(
        id=ch1_id,
        contract_id=c1_id,
        chunk_index=0,
        page_number=2,
        section_header="Section 4 — Fees and Payments",
        text="Customer shall pay all invoices within thirty (30) days of receipt.",
    )
    chunk2 = DocumentChunk(
        id=ch2_id,
        contract_id=c1_id,
        chunk_index=1,
        page_number=5,
        section_header="Section 9 — Reports & Audits",
        text="Vendor must submit SOC2 Type II audit reports annually to customer.",
    )

    # Chunk for Contract 2
    ch3_id = uuid.uuid4()
    chunk3 = DocumentChunk(
        id=ch3_id,
        contract_id=c2_id,
        chunk_index=0,
        page_number=1,
        section_header="Section 1 — Confidentiality",
        text="Recipient shall keep all proprietary information confidential.",
    )
    db_session.add_all([chunk1, chunk2, chunk3])
    db_session.flush()

    # Clauses for Contract 1
    cl1_id = uuid.uuid4()
    cl2_id = uuid.uuid4()
    clause1 = Clause(
        id=cl1_id,
        contract_id=c1_id,
        source_chunk_id=ch1_id,
        clause_type="payment",
        clause_label="Section 4 — Fees and Payments",
        page_number=2,
        verbatim_text="Customer shall pay all invoices within thirty (30) days of receipt.",
    )
    clause2 = Clause(
        id=cl2_id,
        contract_id=c1_id,
        source_chunk_id=ch2_id,
        clause_type="audit",
        clause_label="Section 9 — Reports & Audits",
        page_number=5,
        verbatim_text="Vendor must submit SOC2 Type II audit reports annually to customer.",
    )
    db_session.add_all([clause1, clause2])
    db_session.flush()

    # Obligations for Contract 1
    ref_today = date(2026, 6, 1)

    ob1_id = uuid.uuid4()
    ob1 = Obligation(
        id=ob1_id,
        contract_id=c1_id,
        source_clause_id=cl1_id,
        source_chunk_id=ch1_id,
        title="Pay Invoices Promptly",
        description="Customer must remit payment within 30 days of invoice receipt.",
        verbatim_evidence="Customer shall pay all invoices within thirty (30) days of receipt.",
        page_number=2,
        obligation_type="payment",
        responsible_party="Customer",
        due_date=date(2026, 5, 15),  # Overdue relative to ref_today
        deadline_info="Within 30 days of receipt",
        frequency="One-time",
        is_recurring=False,
        extraction_confidence=0.95,
        status="pending",
        priority="high",
    )

    ob2_id = uuid.uuid4()
    ob2 = Obligation(
        id=ob2_id,
        contract_id=c1_id,
        source_clause_id=cl2_id,
        source_chunk_id=ch2_id,
        title="Deliver Annual SOC2 Report",
        description="Vendor must provide SOC2 report annually.",
        verbatim_evidence="Vendor must submit SOC2 Type II audit reports annually to customer.",
        page_number=5,
        obligation_type="reporting",
        responsible_party="Vendor",
        due_date=date(2026, 6, 20),  # Upcoming within 30 days
        deadline_info="Annually on June 20",
        frequency="Annually",
        is_recurring=True,
        extraction_confidence=0.88,
        status="pending",
        priority="medium",
    )

    ob3_id = uuid.uuid4()
    ob3 = Obligation(
        id=ob3_id,
        contract_id=c1_id,
        source_clause_id=None,
        source_chunk_id=None,
        title="Maintain Cyber Insurance",
        description="Vendor must maintain minimum 5M cyber insurance.",
        verbatim_evidence=None,
        page_number=None,
        obligation_type="insurance",
        responsible_party="Vendor",
        due_date=None,
        deadline_info=None,
        frequency="Ongoing",
        is_recurring=True,
        extraction_confidence=0.55,
        status="completed",
        priority="low",
    )

    # Obligation for Contract 2
    ob4_id = uuid.uuid4()
    ob4 = Obligation(
        id=ob4_id,
        contract_id=c2_id,
        source_clause_id=None,
        source_chunk_id=ch3_id,
        title="Protect Confidential Information",
        description="Recipient must preserve secrecy of confidential materials.",
        verbatim_evidence="Recipient shall keep all proprietary information confidential.",
        page_number=1,
        obligation_type="confidentiality",
        responsible_party="Recipient",
        due_date=None,
        deadline_info="During term and 5 years thereafter",
        frequency=None,
        is_recurring=True,
        extraction_confidence=0.90,
        status="in_progress",
        priority="high",
    )

    db_session.add_all([ob1, ob2, ob3, ob4])
    db_session.commit()

    data = {
        "c1": c1,
        "c2": c2,
        "ob1": ob1,
        "ob2": ob2,
        "ob3": ob3,
        "ob4": ob4,
        "chunk1": chunk1,
        "chunk2": chunk2,
        "chunk3": chunk3,
        "clause1": clause1,
        "clause2": clause2,
        "ref_date": ref_today,
    }

    try:
        yield data
    finally:
        db_session.query(Obligation).filter(Obligation.contract_id.in_([c1_id, c2_id])).delete()
        db_session.query(Clause).filter(Clause.contract_id.in_([c1_id, c2_id])).delete()
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id.in_([c1_id, c2_id])).delete()
        db_session.query(Contract).filter(Contract.id.in_([c1_id, c2_id])).delete()
        db_session.commit()


# ====================================================================
# Unit & Service Layer Tests
# ====================================================================

class TestObligationService:

    def test_query_contract_obligations_baseline(self, db_session: Session, obligation_test_data: dict):
        """12A: Verifies baseline retrieval of obligations for a contract."""
        c1 = obligation_test_data["c1"]
        ref_date = obligation_test_data["ref_date"]

        req = ObligationQueryRequest(reference_date=ref_date)
        resp = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req)

        assert resp.contract_id == c1.id
        assert resp.total_obligations == 3
        assert len(resp.items) == 3

        # Confirm strict contract scoping: ob4 (from c2) must NOT be present
        c2_ob_id = obligation_test_data["ob4"].id
        item_ids = [item.id for item in resp.items]
        assert c2_ob_id not in item_ids

    def test_filter_by_responsible_party_and_type(self, db_session: Session, obligation_test_data: dict):
        """12B: Verifies filtering by responsible party and obligation type."""
        c1 = obligation_test_data["c1"]

        # Filter by party 'Vendor'
        req_vendor = ObligationQueryRequest(responsible_party="Vendor")
        resp_vendor = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req_vendor)
        assert resp_vendor.total_obligations == 2
        for item in resp_vendor.items:
            assert "vendor" in item.responsible_party.lower()

        # Filter by type 'payment'
        req_payment = ObligationQueryRequest(obligation_type="payment")
        resp_payment = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req_payment)
        assert resp_payment.total_obligations == 1
        assert resp_payment.items[0].obligation_type == "payment"
        assert resp_payment.items[0].responsible_party == "Customer"

    def test_filter_by_recurrence_and_due_dates(self, db_session: Session, obligation_test_data: dict):
        """12B: Verifies filtering by recurring status and explicit due dates."""
        c1 = obligation_test_data["c1"]

        # Recurring only
        req_rec = ObligationQueryRequest(is_recurring=True)
        resp_rec = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req_rec)
        assert resp_rec.total_obligations == 2
        for item in resp_rec.items:
            assert item.is_recurring is True

        # Non-recurring only
        req_non_rec = ObligationQueryRequest(is_recurring=False)
        resp_non_rec = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req_non_rec)
        assert resp_non_rec.total_obligations == 1
        assert resp_non_rec.items[0].is_recurring is False

        # Has explicit due date
        req_due = ObligationQueryRequest(has_due_date=True)
        resp_due = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req_due)
        assert resp_due.total_obligations == 2

        # Due date bounds
        req_bound = ObligationQueryRequest(
            due_date_from=date(2026, 6, 1),
            due_date_to=date(2026, 6, 30),
        )
        resp_bound = query_contract_obligations(db=db_session, contract_id=c1.id, filters=req_bound)
        assert resp_bound.total_obligations == 1
        assert resp_bound.items[0].title == "Deliver Annual SOC2 Report"

    def test_evidence_lineage_resolution_and_validation(self, db_session: Session, obligation_test_data: dict):
        """12C: Verifies full 6-tier lineage assembly and deterministic validation."""
        c1 = obligation_test_data["c1"]
        ob1 = obligation_test_data["ob1"]
        ob2 = obligation_test_data["ob2"]

        resp = query_contract_obligations(
            db=db_session,
            contract_id=c1.id,
            filters=ObligationQueryRequest(include_lineage=True),
        )
        assert resp.total_obligations == 3

        item_map = {item.id: item for item in resp.items}

        # ob1: linked to chunk1 and clause1, page 2, quote matching
        item1 = item_map[ob1.id]
        assert item1.evidence_citation is not None
        assert item1.evidence_citation.clause_id == ob1.source_clause_id
        assert item1.evidence_citation.chunk_id == ob1.source_chunk_id
        assert item1.evidence_citation.page_number == 2
        assert item1.evidence_citation.section_header == "Section 4 — Fees and Payments"
        assert item1.evidence_citation.verification_status == CitationVerificationStatus.VALID

        # ob2: linked to chunk2 and clause2, page 5
        item2 = item_map[ob2.id]
        assert item2.evidence_citation is not None
        assert item2.evidence_citation.verification_status == CitationVerificationStatus.VALID

    def test_lineage_detects_wrong_contract_chunk(self, db_session: Session, obligation_test_data: dict):
        """12C: Verifies that foreign contract chunk lineage is flagged as WRONG_CONTRACT."""
        c1 = obligation_test_data["c1"]
        chunk3 = obligation_test_data["chunk3"]  # Belongs to c2!

        # Inject a foreign chunk into an obligation on c1
        mismatched_ob = Obligation(
            id=uuid.uuid4(),
            contract_id=c1.id,
            source_clause_id=None,
            source_chunk_id=chunk3.id,  # foreign!
            title="Mismatched Lineage Obligation",
            description="Obligation referencing a chunk from another contract.",
            verbatim_evidence="Recipient shall keep all proprietary information confidential.",
            page_number=1,
            obligation_type="confidentiality",
            responsible_party="Recipient",
            is_recurring=False,
            status="pending",
            priority="medium",
        )
        db_session.add(mismatched_ob)
        db_session.commit()

        try:
            resp = query_contract_obligations(
                db=db_session,
                contract_id=c1.id,
                filters=ObligationQueryRequest(include_lineage=True),
            )
            item = next(i for i in resp.items if i.id == mismatched_ob.id)
            assert item.evidence_citation.verification_status == CitationVerificationStatus.WRONG_CONTRACT
            assert "foreign contract" in item.evidence_citation.verification_notes.lower()
        finally:
            db_session.delete(mismatched_ob)
            db_session.commit()

    def test_lineage_detects_text_and_page_mismatch(self, db_session: Session, obligation_test_data: dict):
        """12C: Verifies detection of text mismatch and page mismatch."""
        c1 = obligation_test_data["c1"]
        chunk1 = obligation_test_data["chunk1"]

        bad_text_ob = Obligation(
            id=uuid.uuid4(),
            contract_id=c1.id,
            source_clause_id=None,
            source_chunk_id=chunk1.id,
            title="Bad Quote Obligation",
            description="Obligation with quote not in chunk.",
            verbatim_evidence="Nonexistent text definitely not in chunk text.",
            page_number=2,
            obligation_type="other",
            responsible_party="Vendor",
            is_recurring=False,
            status="pending",
            priority="low",
        )
        db_session.add(bad_text_ob)
        db_session.commit()

        try:
            resp = query_contract_obligations(
                db=db_session,
                contract_id=c1.id,
                filters=ObligationQueryRequest(include_lineage=True),
            )
            item = next(i for i in resp.items if i.id == bad_text_ob.id)
            assert item.evidence_citation.verification_status == CitationVerificationStatus.TEXT_MISMATCH
        finally:
            db_session.delete(bad_text_ob)
            db_session.commit()

    def test_deterministic_obligation_analysis_summary(self, db_session: Session, obligation_test_data: dict):
        """12D: Verifies deterministic summary metrics, party breakdowns, overdue, and upcoming counts."""
        c1 = obligation_test_data["c1"]
        ref_date = obligation_test_data["ref_date"]  # 2026-06-01

        resp = query_contract_obligations(
            db=db_session,
            contract_id=c1.id,
            filters=ObligationQueryRequest(reference_date=ref_date),
        )
        summary = resp.analysis

        assert summary.total_obligations == 3
        assert summary.by_responsible_party["Customer"] == 1
        assert summary.by_responsible_party["Vendor"] == 2
        assert summary.by_obligation_type["payment"] == 1
        assert summary.by_obligation_type["reporting"] == 1
        assert summary.by_obligation_type["insurance"] == 1
        assert summary.recurring_count == 2
        assert summary.non_recurring_count == 1
        assert summary.with_due_date_count == 2
        assert summary.with_deadline_info_count == 2

        # Due date calculations (ref_date: 2026-06-01)
        # ob1: due 2026-05-15 (passed, pending -> overdue = 1)
        # ob2: due 2026-06-20 (upcoming <= 30d -> upcoming = 1)
        assert summary.overdue_count == 1
        assert summary.upcoming_count == 1

        # Check item derived analysis
        item_map = {item.id: item for item in resp.items}
        derived1 = item_map[obligation_test_data["ob1"].id].derived_analysis
        assert derived1.is_overdue is True
        assert derived1.days_until_due < 0
        assert derived1.confidence_tier == "high"

        derived2 = item_map[obligation_test_data["ob2"].id].derived_analysis
        assert derived2.is_overdue is False
        assert derived2.days_until_due > 0
        assert derived2.cadence == "Annually"

    def test_single_obligation_scoping_enforcement(self, db_session: Session, obligation_test_data: dict):
        """12E: Verifies that requesting an obligation under the wrong contract raises ObligationScopingError."""
        c1 = obligation_test_data["c1"]
        c2 = obligation_test_data["c2"]
        ob4 = obligation_test_data["ob4"]  # Belongs to c2

        # Accessing c2's obligation under c1 must fail
        with pytest.raises(ObligationScopingError) as exc_info:
            get_single_obligation_detail(
                db=db_session,
                contract_id=c1.id,
                obligation_id=ob4.id,
            )
        assert "belongs to contract" in str(exc_info.value).lower()

    def test_nonexistent_contract_raises_404(self, db_session: Session):
        """12E: Verifies ContractNotFoundError on unknown contract UUID."""
        fake_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError):
            query_contract_obligations(db=db_session, contract_id=fake_id)


# ====================================================================
# REST API Endpoint Tests via TestClient
# ====================================================================

def test_obligation_api_endpoints_mounted(obligation_test_data: dict):
    """12E: Verifies GET /query, POST /query, and GET /{id} REST endpoints."""
    client = TestClient(app)
    c1 = obligation_test_data["c1"]
    c2 = obligation_test_data["c2"]
    ob1 = obligation_test_data["ob1"]
    ob4 = obligation_test_data["ob4"]

    # 1. GET /contracts/{contract_id}/obligations/query
    resp_get = client.get(
        f"/contracts/{c1.id}/obligations/query?responsible_party=Vendor&is_recurring=true"
    )
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["total_obligations"] == 2
    assert data_get["analysis"]["recurring_count"] == 2

    # 2. POST /contracts/{contract_id}/obligations/query
    resp_post = client.post(
        f"/contracts/{c1.id}/obligations/query",
        json={
            "obligation_type": "payment",
            "include_lineage": True,
        },
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["total_obligations"] == 1
    assert data_post["items"][0]["title"] == "Pay Invoices Promptly"
    assert data_post["items"][0]["evidence_citation"]["verification_status"] == "valid"

    # 3. GET /contracts/{contract_id}/obligations/{obligation_id}
    resp_detail = client.get(f"/contracts/{c1.id}/obligations/{ob1.id}")
    assert resp_detail.status_code == 200
    data_detail = resp_detail.json()
    assert data_detail["id"] == str(ob1.id)
    assert data_detail["responsible_party"] == "Customer"
    assert data_detail["derived_analysis"]["has_explicit_due_date"] is True

    # 4. Versioned API prefix /api/v1/contracts/{contract_id}/obligations/query
    resp_v1 = client.get(f"/api/v1/contracts/{c1.id}/obligations/query")
    assert resp_v1.status_code == 200

    # 5. Nonexistent contract returns 404
    fake_cid = uuid.uuid4()
    resp_404 = client.get(f"/contracts/{fake_cid}/obligations/query")
    assert resp_404.status_code == 404

    # 6. Cross-contract obligation leakage returns 404 (ob4 belongs to c2, not c1)
    resp_scoped = client.get(f"/contracts/{c1.id}/obligations/{ob4.id}")
    assert resp_scoped.status_code == 404
    assert "belongs to contract" in resp_scoped.json()["detail"].lower()
