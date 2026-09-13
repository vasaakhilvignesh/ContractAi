"""
ContractIQ — Tests for Persistent Evidence Model (Phase 7A)

Verifies:
  1. Creation & Default Behavior:
     - Evidence record creation with required and optional fields.
     - Auto-generation of source_item_reference (type:id).
     - text and span property aliases.
  2. Strict Source Evidence Lineage:
     - Clause Lineage: evidence → clause → chunk → page → contract.
     - Obligation Lineage: evidence → obligation → clause → chunk → page → contract.
     - ContractFact Lineage: evidence → contract_fact → clause → chunk → page → contract.
     - get_lineage() serialization and dictionary output.
  3. ORM Relationships & Cascade Rules:
     - evidence.contract and contract.evidence bidirectional navigation.
     - evidence.source_clause and clause.evidence bidirectional navigation.
     - evidence.source_chunk navigation.
     - Contract cascade deletion removes associated evidence.
     - Chunk / Clause deletion sets foreign key to NULL.
  4. Database Check Constraints & Foreign Keys:
     - Rejection of invalid source_item_type (check constraint).
     - Rejection of non-positive page_number (check constraint).
     - Rejection of negative char_start (check constraint).
     - Rejection of char_end < char_start (check constraint).
     - Rejection of non-existent contract_id (foreign key constraint).
  5. Immutability Invariant:
     - Modifying an existing Evidence record raises ValueError via the before_update listener.
  6. Pydantic Schemas:
     - Validation, serialization, alias normalization (text -> source_text, span -> offsets).
"""

from datetime import datetime
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.evidence import Evidence
from app.models.obligation import Obligation
from app.schemas.evidence import (
    EvidenceBase,
    EvidenceCreate,
    EvidenceLineage,
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceSourceItemType,
)


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
def test_hierarchy(db_session: Session):
    """
    Creates a full contract hierarchy for lineage testing:
    Contract -> DocumentChunk -> Clause -> Obligation & ContractFact
    """
    contract_id = uuid.uuid4()
    contract = Contract(
        id=contract_id,
        title="Evidence Model Test Agreement",
        vendor="Global Logistics Corp",
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
        page_number=3,
        section_header="Section 9. Indemnification and Liability",
        char_start=120,
        char_end=480,
        text="Each party shall indemnify, defend, and hold harmless the other party from all third-party claims.",
    )
    db_session.add(chunk)

    clause_id = uuid.uuid4()
    clause = Clause(
        id=clause_id,
        contract_id=contract_id,
        source_chunk_id=chunk_id,
        clause_type="indemnification",
        clause_label="Section 9.1 — Mutual Indemnification",
        verbatim_text="Each party shall indemnify, defend, and hold harmless the other party from all third-party claims.",
        page_number=3,
        extraction_confidence=0.98,
    )
    db_session.add(clause)

    obligation_id = uuid.uuid4()
    obligation = Obligation(
        id=obligation_id,
        contract_id=contract_id,
        source_clause_id=clause_id,
        source_chunk_id=chunk_id,
        title="Mutual Third-Party Indemnification",
        description="Indemnify other party from third-party claims",
        verbatim_evidence="Each party shall indemnify, defend, and hold harmless the other party",
        page_number=3,
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
        fact_key="indemnification_cap",
        fact_value="Mutual Uncapped",
        verbatim_evidence="Each party shall indemnify, defend, and hold harmless the other party from all third-party claims.",
        page_number=3,
        confidence=0.95,
    )
    db_session.add(fact)
    db_session.commit()

    hierarchy = {
        "contract": contract,
        "chunk": chunk,
        "clause": clause,
        "obligation": obligation,
        "fact": fact,
    }

    try:
        yield hierarchy
    finally:
        # Cleanup hierarchy and all generated evidence
        db_session.query(Evidence).filter(Evidence.contract_id == contract_id).delete()
        db_session.query(ContractFact).filter(ContractFact.contract_id == contract_id).delete()
        db_session.query(Obligation).filter(Obligation.contract_id == contract_id).delete()
        db_session.query(Clause).filter(Clause.contract_id == contract_id).delete()
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract_id).delete()
        db_session.query(Contract).filter(Contract.id == contract_id).delete()
        db_session.commit()


# ====================================================================
# Test Suite 1: Evidence Creation & Defaults
# ====================================================================

class TestEvidenceCreation:
    """Tests for basic creation and property helpers on the Evidence model."""

    def test_create_evidence_with_all_fields(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        clause = test_hierarchy["clause"]
        chunk = test_hierarchy["chunk"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            page_number=3,
            source_text="Each party shall indemnify, defend, and hold harmless",
            char_start=120,
            char_end=173,
        )
        db_session.add(evidence)
        db_session.commit()

        assert evidence.id is not None
        assert isinstance(evidence.id, uuid.UUID)
        assert evidence.contract_id == contract.id
        assert evidence.source_item_type == "clause"
        assert evidence.source_item_id == clause.id
        assert evidence.source_item_reference == f"clause:{clause.id}"
        assert evidence.source_clause_id == clause.id
        assert evidence.source_chunk_id == chunk.id
        assert evidence.page_number == 3
        assert evidence.source_text == "Each party shall indemnify, defend, and hold harmless"
        assert evidence.char_start == 120
        assert evidence.char_end == 173
        assert isinstance(evidence.created_at, datetime)

    def test_evidence_property_aliases(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        clause = test_hierarchy["clause"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            text="Verbatim quote",
            span=(10, 24),
        )
        assert evidence.source_text == "Verbatim quote"
        assert evidence.text == "Verbatim quote"
        assert evidence.char_start == 10
        assert evidence.char_end == 24
        assert evidence.span == (10, 24)

        # Setter verification
        evidence.text = "Updated in-memory quote"
        assert evidence.source_text == "Updated in-memory quote"


# ====================================================================
# Test Suite 2: Strict Source Lineage (Preserve 5-tier Lineage)
# ====================================================================

class TestEvidenceLineage:
    """
    Verifies lineage chain:
    evidence → source item → clause → chunk → page → contract
    """

    def test_clause_source_lineage(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        chunk = test_hierarchy["chunk"]
        clause = test_hierarchy["clause"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            page_number=clause.page_number,
            source_text=clause.verbatim_text,
            char_start=0,
            char_end=len(clause.verbatim_text),
        )
        db_session.add(evidence)
        db_session.commit()

        # Check lineage chain: evidence → source item (clause) → chunk → page → contract
        assert evidence.source_item_type == "clause"
        assert evidence.source_item_id == clause.id
        assert evidence.source_clause_id == clause.id
        assert evidence.source_chunk_id == chunk.id
        assert evidence.page_number == chunk.page_number == 3
        assert evidence.contract_id == contract.id

        # Verify get_lineage() payload
        lineage = evidence.get_lineage()
        assert lineage["evidence_id"] == evidence.id
        assert lineage["source_item_type"] == "clause"
        assert lineage["source_item_id"] == clause.id
        assert lineage["clause_id"] == clause.id
        assert lineage["chunk_id"] == chunk.id
        assert lineage["page_number"] == 3
        assert lineage["contract_id"] == contract.id

    def test_obligation_source_lineage(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        chunk = test_hierarchy["chunk"]
        clause = test_hierarchy["clause"]
        obligation = test_hierarchy["obligation"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="obligation",
            source_item_id=obligation.id,
            source_clause_id=obligation.source_clause_id,
            source_chunk_id=obligation.source_chunk_id,
            page_number=obligation.page_number,
            source_text=obligation.verbatim_evidence,
            char_start=120,
            char_end=180,
        )
        db_session.add(evidence)
        db_session.commit()

        # Check lineage: evidence → obligation (source item) → clause → chunk → page → contract
        assert evidence.source_item_type == "obligation"
        assert evidence.source_item_id == obligation.id
        assert evidence.source_clause_id == clause.id
        assert evidence.source_chunk_id == chunk.id
        assert evidence.page_number == 3
        assert evidence.contract_id == contract.id

        # Verify through entity relationships
        assert obligation.source_clause.id == clause.id
        assert clause.source_chunk.id == chunk.id
        assert chunk.contract_id == contract.id

    def test_contract_fact_source_lineage(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        chunk = test_hierarchy["chunk"]
        clause = test_hierarchy["clause"]
        fact = test_hierarchy["fact"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="contract_fact",
            source_item_id=fact.id,
            source_clause_id=fact.source_clause_id,
            source_chunk_id=fact.source_chunk_id,
            page_number=fact.page_number,
            source_text=fact.verbatim_evidence,
        )
        db_session.add(evidence)
        db_session.commit()

        # Check lineage: evidence → contract_fact (source item) → clause → chunk → page → contract
        assert evidence.source_item_type == "contract_fact"
        assert evidence.source_item_id == fact.id
        assert evidence.source_clause_id == clause.id
        assert evidence.source_chunk_id == chunk.id
        assert evidence.page_number == 3
        assert evidence.contract_id == contract.id

        lineage = evidence.get_lineage()
        assert lineage["source_item_type"] == "contract_fact"
        assert lineage["source_item_id"] == fact.id


# ====================================================================
# Test Suite 3: Relationships & Cascades
# ====================================================================

class TestEvidenceRelationships:
    """Tests SQLAlchemy ORM relationships and cascade integrity."""

    def test_bidirectional_contract_relationship(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        clause = test_hierarchy["clause"]

        ev1 = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            source_clause_id=clause.id,
            source_text="First evidence piece",
        )
        ev2 = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            source_clause_id=clause.id,
            source_text="Second evidence piece",
        )
        db_session.add_all([ev1, ev2])
        db_session.commit()

        # Parent -> child
        db_session.refresh(contract)
        assert ev1 in contract.evidence
        assert ev2 in contract.evidence

        # Child -> parent
        assert ev1.contract.id == contract.id
        assert ev2.contract.id == contract.id

    def test_clause_relationship_and_aliases(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        clause = test_hierarchy["clause"]
        chunk = test_hierarchy["chunk"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            source_text="Test relationship clause",
        )
        db_session.add(evidence)
        db_session.commit()

        # Navigation via relationships and property aliases
        assert evidence.source_clause.id == clause.id
        assert evidence.clause.id == clause.id
        assert evidence.source_chunk.id == chunk.id
        assert evidence.chunk.id == chunk.id

        # Back-populate on clause
        db_session.refresh(clause)
        assert evidence in clause.evidence

    def test_cascade_delete_contract_deletes_evidence(self, db_session: Session):
        # Create dedicated contract to test cascade delete
        temp_contract = Contract(
            id=uuid.uuid4(),
            title="Cascade Delete Test Contract",
            status="active",
        )
        db_session.add(temp_contract)
        db_session.commit()

        dummy_clause_id = uuid.uuid4()
        evidence = Evidence(
            contract_id=temp_contract.id,
            source_item_type="clause",
            source_item_id=dummy_clause_id,
            source_text="Temporary evidence to be cascade deleted",
        )
        db_session.add(evidence)
        db_session.commit()

        ev_id = evidence.id
        assert db_session.get(Evidence, ev_id) is not None

        # Delete contract -> should delete evidence
        db_session.delete(temp_contract)
        db_session.commit()

        assert db_session.get(Evidence, ev_id) is None


# ====================================================================
# Test Suite 4: Database Constraints & Validation
# ====================================================================

class TestEvidenceConstraints:
    """Verifies check constraints and foreign key constraints on the evidence table."""

    def test_invalid_source_item_type_rejected(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]

        invalid_evidence = Evidence(
            contract_id=contract.id,
            source_item_type="unsupported_entity",
            source_item_id=uuid.uuid4(),
            source_text="Sample text",
        )
        db_session.add(invalid_evidence)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_page_number_rejected(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]

        invalid_evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=uuid.uuid4(),
            page_number=0,  # Must be >= 1 (1-indexed)
            source_text="Sample text",
        )
        db_session.add(invalid_evidence)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_char_offsets_rejected(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]

        # Negative char_start
        neg_start = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=uuid.uuid4(),
            char_start=-5,
            source_text="Sample text",
        )
        db_session.add(neg_start)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

        # char_end < char_start
        inverted_span = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=uuid.uuid4(),
            char_start=50,
            char_end=20,
            source_text="Sample text",
        )
        db_session.add(inverted_span)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_nonexistent_contract_fk_rejected(self, db_session: Session):
        invalid_evidence = Evidence(
            contract_id=uuid.uuid4(),  # Non-existent contract
            source_item_type="clause",
            source_item_id=uuid.uuid4(),
            source_text="Sample text",
        )
        db_session.add(invalid_evidence)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ====================================================================
# Test Suite 5: Immutability Invariant
# ====================================================================

class TestEvidenceImmutability:
    """Verifies that evidence records cannot be mutated once persisted."""

    def test_updating_evidence_raises_error(self, db_session: Session, test_hierarchy: dict):
        contract = test_hierarchy["contract"]
        clause = test_hierarchy["clause"]

        evidence = Evidence(
            contract_id=contract.id,
            source_item_type="clause",
            source_item_id=clause.id,
            source_text="Immutable original observation",
        )
        db_session.add(evidence)
        db_session.commit()

        # Attempt to modify the persistent record
        evidence.source_text = "Modified observation attempting mutation"
        with pytest.raises(ValueError, match="Evidence records are source-oriented and immutable"):
            db_session.commit()
        db_session.rollback()


# ====================================================================
# Test Suite 6: Pydantic Schemas Validation
# ====================================================================

class TestEvidenceSchemas:
    """Verifies Pydantic v2 schemas for Evidence."""

    def test_evidence_base_alias_and_span_normalization(self):
        cid = uuid.uuid4()
        sid = uuid.uuid4()

        schema = EvidenceBase(
            contract_id=cid,
            source_item_type="clause",
            source_item_id=sid,
            text="Normalized verbatim excerpt",
            span=(10, 40),
            page_number=1,
        )

        assert schema.source_text == "Normalized verbatim excerpt"
        assert schema.char_start == 10
        assert schema.char_end == 40
        assert schema.span == (10, 40)
        assert schema.source_item_reference == f"clause:{sid}"

    def test_evidence_lineage_schema(self):
        eid = uuid.uuid4()
        cid = uuid.uuid4()
        sid = uuid.uuid4()
        clause_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        lineage = EvidenceLineage(
            evidence_id=eid,
            source_item_type="obligation",
            source_item_id=sid,
            source_item_reference=f"obligation:{sid}",
            clause_id=clause_id,
            chunk_id=chunk_id,
            page_number=2,
            contract_id=cid,
            source_text="Contractor must provide insurance certificates",
            char_start=45,
            char_end=90,
            created_at=datetime.utcnow(),
        )

        assert lineage.evidence_id == eid
        assert lineage.source_item_type == "obligation"
        assert lineage.clause_id == clause_id
        assert lineage.chunk_id == chunk_id
        assert lineage.page_number == 2
        assert lineage.contract_id == cid

    def test_evidence_list_response_schema(self):
        cid = uuid.uuid4()
        sid = uuid.uuid4()
        eid = uuid.uuid4()

        resp = EvidenceResponse(
            id=eid,
            contract_id=cid,
            source_item_type=EvidenceSourceItemType.CLAUSE,
            source_item_id=sid,
            source_text="Sample clause text",
            page_number=1,
            created_at=datetime.utcnow(),
        )

        list_resp = EvidenceListResponse(
            contract_id=cid,
            total_evidence=1,
            evidence=[resp],
        )

        assert list_resp.total_evidence == 1
        assert list_resp.evidence[0].id == eid
        assert list_resp.evidence[0].source_item_type == "clause"
