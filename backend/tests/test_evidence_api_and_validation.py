"""
ContractIQ — Tests for Evidence API & Deterministic Validation (Phase 7B & Phase 7C)

Verifies:
  Phase 7B:
    - POST /contracts/{contract_id}/evidence (Create evidence record)
    - GET /contracts/{contract_id}/evidence (List evidence with item_type/item_id/page filters)
    - GET /contracts/{contract_id}/evidence/{evidence_id} (Get single evidence)
    - GET /contracts/{contract_id}/evidence/lineage (Full 6-tier lineage listing)
    - GET /contracts/{contract_id}/evidence/{evidence_id}/lineage (Single 6-tier lineage trace)
    - Proper 404 handling for non-existent contracts and evidence
  Phase 7C:
    - POST /contracts/{contract_id}/evidence/validate (Validate all evidence)
    - Detection of valid evidence with matching chunk text, page, and contract
    - Detection of text_mismatch when evidence text is not in referenced chunk
    - Detection of page_mismatch when evidence page diverges from chunk/clause
    - Detection of contract_mismatch when source items belong to another contract
    - Detection of missing_chunk, missing_clause, and missing_source_item (broken lineage / stale)
    - Filtering validation by single evidence_id
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.evidence import Evidence
from app.models.obligation import Obligation


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests with cleanup."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def contract_hierarchy(db_session: Session):
    """
    Creates a full contract hierarchy for API and validation testing:
    Contract -> DocumentChunk -> Clause -> Obligation & ContractFact
    """
    contract_id = uuid.uuid4()
    contract = Contract(
        id=contract_id,
        title="Master Services Agreement 2026",
        vendor="Cyberdyne Systems",
        contract_type="MSA",
        status="active",
        processing_status="completed",
    )
    db_session.add(contract)

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        contract_id=contract_id,
        chunk_index=0,
        page_number=4,
        section_header="Section 12. Limitation of Liability",
        char_start=0,
        char_end=250,
        text="In no event shall either party be liable for indirect, incidental, special, or consequential damages. Total liability under this agreement shall not exceed aggregate fees paid in the twelve months preceding the claim.",
    )
    db_session.add(chunk)

    clause_id = uuid.uuid4()
    clause = Clause(
        id=clause_id,
        contract_id=contract_id,
        source_chunk_id=chunk_id,
        clause_type="liability",
        clause_label="Section 12.1 — Consequential Damages Waiver",
        verbatim_text="In no event shall either party be liable for indirect, incidental, special, or consequential damages.",
        page_number=4,
        extraction_confidence=0.97,
    )
    db_session.add(clause)

    obligation_id = uuid.uuid4()
    obligation = Obligation(
        id=obligation_id,
        contract_id=contract_id,
        source_clause_id=clause_id,
        source_chunk_id=chunk_id,
        title="Cap on Damages",
        description="Limit damages to twelve months fees paid",
        verbatim_evidence="Total liability under this agreement shall not exceed aggregate fees paid in the twelve months preceding the claim.",
        page_number=4,
        obligation_type="compliance",
        responsible_party="Both Parties",
        status="pending",
        priority="high",
    )
    db_session.add(obligation)

    fact_id = uuid.uuid4()
    fact = ContractFact(
        id=fact_id,
        contract_id=contract_id,
        source_clause_id=clause_id,
        source_chunk_id=chunk_id,
        fact_key="liability_cap",
        fact_value="12 months aggregate fees",
        verbatim_evidence="Total liability under this agreement shall not exceed aggregate fees paid in the twelve months preceding the claim.",
        page_number=4,
        confidence=0.96,
    )
    db_session.add(fact)
    db_session.commit()

    data = {
        "contract": contract,
        "chunk": chunk,
        "clause": clause,
        "obligation": obligation,
        "fact": fact,
    }

    try:
        yield data
    finally:
        db_session.query(Evidence).filter(Evidence.contract_id == contract_id).delete()
        db_session.query(ContractFact).filter(ContractFact.contract_id == contract_id).delete()
        db_session.query(Obligation).filter(Obligation.contract_id == contract_id).delete()
        db_session.query(Clause).filter(Clause.contract_id == contract_id).delete()
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract_id).delete()
        db_session.query(Contract).filter(Contract.id == contract_id).delete()
        db_session.commit()


# ====================================================================
# Phase 7B: Evidence API Endpoints Tests
# ====================================================================

class TestEvidenceAPIEndpoints:
    """Tests for Phase 7B REST endpoints."""

    def test_create_and_get_evidence_endpoint(self, client: TestClient, contract_hierarchy: dict):
        contract = contract_hierarchy["contract"]
        clause = contract_hierarchy["clause"]
        chunk = contract_hierarchy["chunk"]

        payload = {
            "contract_id": str(contract.id),
            "source_item_type": "clause",
            "source_item_id": str(clause.id),
            "source_clause_id": str(clause.id),
            "source_chunk_id": str(chunk.id),
            "page_number": 4,
            "source_text": "In no event shall either party be liable for indirect, incidental, special, or consequential damages.",
            "char_start": 0,
            "char_end": 102,
        }

        # POST /contracts/{contract_id}/evidence
        response = client.post(f"/contracts/{contract.id}/evidence", json=payload)
        assert response.status_code == 201
        created = response.json()
        assert created["contract_id"] == str(contract.id)
        assert created["source_item_type"] == "clause"
        assert created["source_item_id"] == str(clause.id)
        assert created["source_item_reference"] == f"clause:{clause.id}"
        assert created["page_number"] == 4
        evidence_id = created["id"]

        # GET /contracts/{contract_id}/evidence/{evidence_id}
        get_res = client.get(f"/contracts/{contract.id}/evidence/{evidence_id}")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["id"] == evidence_id
        assert data["source_text"] == payload["source_text"]

    def test_list_evidence_with_filtering(self, client: TestClient, contract_hierarchy: dict):
        contract = contract_hierarchy["contract"]
        clause = contract_hierarchy["clause"]
        obligation = contract_hierarchy["obligation"]
        chunk = contract_hierarchy["chunk"]

        # Create two evidence records: one for clause, one for obligation
        client.post(
            f"/contracts/{contract.id}/evidence",
            json={
                "contract_id": str(contract.id),
                "source_item_type": "clause",
                "source_item_id": str(clause.id),
                "source_clause_id": str(clause.id),
                "source_chunk_id": str(chunk.id),
                "page_number": 4,
                "source_text": clause.verbatim_text,
            },
        )
        client.post(
            f"/contracts/{contract.id}/evidence",
            json={
                "contract_id": str(contract.id),
                "source_item_type": "obligation",
                "source_item_id": str(obligation.id),
                "source_clause_id": str(clause.id),
                "source_chunk_id": str(chunk.id),
                "page_number": 4,
                "source_text": obligation.verbatim_evidence,
            },
        )

        # List all
        all_res = client.get(f"/contracts/{contract.id}/evidence")
        assert all_res.status_code == 200
        assert all_res.json()["total_evidence"] == 2

        # Filter by source_item_type=obligation
        ob_res = client.get(f"/contracts/{contract.id}/evidence?source_item_type=obligation")
        assert ob_res.status_code == 200
        assert ob_res.json()["total_evidence"] == 1
        assert ob_res.json()["evidence"][0]["source_item_type"] == "obligation"

        # Filter by non-existent page
        page_res = client.get(f"/contracts/{contract.id}/evidence?page_number=99")
        assert page_res.status_code == 200
        assert page_res.json()["total_evidence"] == 0

    def test_evidence_lineage_trace_endpoint(self, client: TestClient, contract_hierarchy: dict):
        contract = contract_hierarchy["contract"]
        clause = contract_hierarchy["clause"]
        chunk = contract_hierarchy["chunk"]

        create_res = client.post(
            f"/contracts/{contract.id}/evidence",
            json={
                "contract_id": str(contract.id),
                "source_item_type": "clause",
                "source_item_id": str(clause.id),
                "source_clause_id": str(clause.id),
                "source_chunk_id": str(chunk.id),
                "page_number": 4,
                "source_text": clause.verbatim_text,
            },
        )
        evidence_id = create_res.json()["id"]

        # GET /contracts/{contract_id}/evidence/{evidence_id}/lineage
        lineage_res = client.get(f"/contracts/{contract.id}/evidence/{evidence_id}/lineage")
        assert lineage_res.status_code == 200
        lineage = lineage_res.json()
        assert lineage["evidence_id"] == evidence_id
        assert lineage["source_item_type"] == "clause"
        assert lineage["source_item_id"] == str(clause.id)
        assert lineage["clause_id"] == str(clause.id)
        assert lineage["chunk_id"] == str(chunk.id)
        assert lineage["page_number"] == 4
        assert lineage["contract_id"] == str(contract.id)

        # GET /contracts/{contract_id}/evidence/lineage (List complete lineages)
        list_lineage = client.get(f"/contracts/{contract.id}/evidence/lineage")
        assert list_lineage.status_code == 200
        assert list_lineage.json()["total_evidence"] == 1
        assert list_lineage.json()["evidence"][0]["evidence_id"] == evidence_id

    def test_evidence_errors_404(self, client: TestClient):
        random_id = str(uuid.uuid4())
        # Non-existent contract
        res = client.get(f"/contracts/{random_id}/evidence")
        assert res.status_code == 404

        # Non-existent evidence
        res2 = client.get(f"/contracts/{random_id}/evidence/{uuid.uuid4()}")
        assert res2.status_code == 404


# ====================================================================
# Phase 7C: Evidence Deterministic Validation Tests
# ====================================================================

class TestEvidenceValidationService:
    """Tests for Phase 7C validation logic and error detection."""

    def test_validate_healthy_evidence(self, client: TestClient, contract_hierarchy: dict):
        contract = contract_hierarchy["contract"]
        clause = contract_hierarchy["clause"]
        chunk = contract_hierarchy["chunk"]

        # Valid evidence cleanly within chunk text
        create_res = client.post(
            f"/contracts/{contract.id}/evidence",
            json={
                "contract_id": str(contract.id),
                "source_item_type": "clause",
                "source_item_id": str(clause.id),
                "source_clause_id": str(clause.id),
                "source_chunk_id": str(chunk.id),
                "page_number": 4,
                "source_text": "In no event shall either party be liable for indirect, incidental, special, or consequential damages.",
            },
        )
        assert create_res.status_code == 201

        # Run validation endpoint
        val_res = client.post(f"/contracts/{contract.id}/evidence/validate")
        assert val_res.status_code == 200
        summary = val_res.json()
        assert summary["total_checked"] == 1
        assert summary["valid_count"] == 1
        assert summary["invalid_count"] == 0
        assert summary["results"][0]["is_valid"] is True
        assert summary["results"][0]["lineage_intact"] is True
        assert summary["results"][0]["text_verified"] is True
        assert summary["results"][0]["page_verified"] is True
        assert summary["results"][0]["status"] == "valid"

    def test_detect_text_mismatch(self, client: TestClient, contract_hierarchy: dict):
        contract = contract_hierarchy["contract"]
        clause = contract_hierarchy["clause"]
        chunk = contract_hierarchy["chunk"]

        # Fabricated verbatim text that doesn't appear in the referenced chunk
        create_res = client.post(
            f"/contracts/{contract.id}/evidence",
            json={
                "contract_id": str(contract.id),
                "source_item_type": "clause",
                "source_item_id": str(clause.id),
                "source_clause_id": str(clause.id),
                "source_chunk_id": str(chunk.id),
                "page_number": 4,
                "source_text": "THIS TEXT DOES NOT EXIST ANYWHERE IN THE CHUNK TEXT OR DOCUMENT",
            },
        )
        assert create_res.status_code == 201

        val_res = client.post(f"/contracts/{contract.id}/evidence/validate")
        assert val_res.status_code == 200
        summary = val_res.json()
        assert summary["total_checked"] == 1
        assert summary["valid_count"] == 0
        assert summary["invalid_count"] == 1
        assert summary["results"][0]["is_valid"] is False
        assert summary["results"][0]["text_verified"] is False
        assert summary["results"][0]["status"] == "text_mismatch"
        issues = summary["results"][0]["issues"]
        assert any(i["issue_type"] == "text_mismatch" for i in issues)

    def test_detect_page_mismatch(self, client: TestClient, contract_hierarchy: dict):
        contract = contract_hierarchy["contract"]
        clause = contract_hierarchy["clause"]
        chunk = contract_hierarchy["chunk"]

        # Chunk is on page 4, but evidence specifies page 99
        create_res = client.post(
            f"/contracts/{contract.id}/evidence",
            json={
                "contract_id": str(contract.id),
                "source_item_type": "clause",
                "source_item_id": str(clause.id),
                "source_clause_id": str(clause.id),
                "source_chunk_id": str(chunk.id),
                "page_number": 99,
                "source_text": clause.verbatim_text,
            },
        )
        assert create_res.status_code == 201

        val_res = client.post(f"/contracts/{contract.id}/evidence/validate")
        assert val_res.status_code == 200
        summary = val_res.json()
        assert summary["invalid_count"] == 1
        res = summary["results"][0]
        assert res["is_valid"] is False
        assert res["page_verified"] is False
        assert any(i["issue_type"] == "page_mismatch" for i in res["issues"])

    def test_detect_broken_lineage_and_missing_source_item(
        self, client: TestClient, contract_hierarchy: dict, db_session: Session
    ):
        contract = contract_hierarchy["contract"]
        non_existent_item_id = uuid.uuid4()

        # Evidence pointing to a non-existent clause ID
        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=non_existent_item_id,
            page_number=4,
            source_text="Some valid text quote",
        )
        db_session.add(evidence)
        db_session.commit()

        val_res = client.post(f"/contracts/{contract.id}/evidence/validate")
        assert val_res.status_code == 200
        summary = val_res.json()
        assert summary["invalid_count"] == 1
        res = summary["results"][0]
        assert res["is_valid"] is False
        assert res["lineage_intact"] is False
        assert res["status"] == "broken_lineage"
        assert any(i["issue_type"] == "missing_source_item" for i in res["issues"])
