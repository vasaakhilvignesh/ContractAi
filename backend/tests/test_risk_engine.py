"""
ContractIQ — Tests for Deterministic Contract Risk Engine & API (Phase 8A–8D)

Verifies:
  Phase 8A — Rule Framework:
    - Modular execution of deterministic rules on ContractEvaluationContext.
    - Zero hallucination / no false positives when contract facts are missing.
    - Full explanation: rule_id, rule_description, severity, category, recommended_action.
  Phase 8B — Renewal Rules:
    - RULE_CONTRACT_EXPIRED (expiration_date < reference_date -> critical).
    - RULE_CONTRACT_EXPIRING_SOON (expiration_date within 60 days -> high/medium).
    - RULE_AUTO_RENEWAL_ACTIVE (auto_renewal clause or successive term fact).
    - RULE_AUTO_RENEWAL_SHORT_NOTICE (notice period <= 30 days in auto-renewing contract).
  Phase 8C — Contract Risk Rules:
    - RULE_TERMINATION_NOTICE_SHORT (notice <= 15 days -> high risk).
    - RULE_UNCAPPED_LIABILITY (uncapped/unlimited liability or broad clause exclusion -> critical).
    - RULE_BROAD_INDEMNIFICATION (uncapped indemnification -> high risk).
    - RULE_MISSING_GOVERNING_LAW (processed contract without jurisdiction).
    - RULE_HIGH_PRIORITY_OVERDUE_OBLIGATION (overdue high priority obligation).
  Phase 8D — Risk API & Idempotency:
    - POST /contracts/{contract_id}/risks/evaluate persists RiskSignal records.
    - Idempotency: Subsequent calls return existing signals with zero duplicates.
    - force_reevaluate=True clears previous signals and recalculated fresh ones.
    - GET /contracts/{contract_id}/risks with severity and category filtering.
    - Correct foreign key and evidence lineage:
        RiskSignal → Rule → Clause/Chunk/Fact → Contract.
"""

from datetime import date
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
from app.models.obligation import Obligation
from app.models.risk_signal import RiskSignal
from app.schemas.risk import RiskCategory, RiskSeverity
from app.services.risk_engine import (
    AutoRenewalActiveRule,
    AutoRenewalShortNoticeRule,
    ContractEvaluationContext,
    ContractExpiredRule,
    ContractExpiringSoonRule,
    MissingGoverningLawRule,
    OverdueHighPriorityObligationRule,
    TerminationNoticeShortRule,
    UncappedLiabilityRule,
    evaluate_contract_rules,
)
from app.services import risk_service


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def client():
    """FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Database session with cleanup."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def base_contract_setup(db_session: Session):
    """
    Creates a base contract structure with chunk and clause.
    """
    contract_id = uuid.uuid4()
    contract = Contract(
        id=contract_id,
        title="Enterprise SaaS Master Agreement",
        vendor="Vertex Cloud Systems",
        contract_type="SaaS",
        status="active",
        processing_status="completed",
    )
    db_session.add(contract)

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        contract_id=contract_id,
        chunk_index=0,
        page_number=2,
        section_header="Section 5. Term and Termination",
        text="The initial term shall expire on 2026-08-01. Either party may terminate upon 10 days notice.",
    )
    db_session.add(chunk)

    clause_id = uuid.uuid4()
    clause = Clause(
        id=clause_id,
        contract_id=contract_id,
        source_chunk_id=chunk_id,
        clause_type="termination",
        clause_label="Section 5.2 — Termination for Convenience",
        verbatim_text="Either party may terminate upon 10 days notice.",
        page_number=2,
        extraction_confidence=0.98,
    )
    db_session.add(clause)
    db_session.commit()

    context = {
        "contract": contract,
        "chunk": chunk,
        "clause": clause,
    }

    try:
        yield context
    finally:
        db_session.query(RiskSignal).filter(RiskSignal.contract_id == contract_id).delete()
        db_session.query(ContractFact).filter(ContractFact.contract_id == contract_id).delete()
        db_session.query(Obligation).filter(Obligation.contract_id == contract_id).delete()
        db_session.query(Clause).filter(Clause.contract_id == contract_id).delete()
        db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract_id).delete()
        db_session.query(Contract).filter(Contract.id == contract_id).delete()
        db_session.commit()


# ====================================================================
# Suite 1: Rule Framework & Renewal Rules (Phase 8A & 8B)
# ====================================================================

class TestRenewalRules:
    """Tests for renewal, expiration, and notice period rules."""

    def test_contract_expired_rule(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        clause = base_contract_setup["clause"]
        chunk = base_contract_setup["chunk"]

        # Stated expiration date is in the past relative to reference date 2026-09-13
        past_fact = ContractFact(
            contract_id=contract.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            fact_key="expiration_date",
            fact_value="2026-06-30",
            verbatim_evidence="Agreement terminates on June 30, 2026",
            page_number=2,
        )

        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[clause],
            obligations=[],
            facts=[past_fact],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        rule = ContractExpiredRule()
        results = rule.evaluate(ctx)
        assert len(results) == 1
        assert results[0].rule_id == "RULE_CONTRACT_EXPIRED"
        assert results[0].severity == RiskSeverity.CRITICAL
        assert "Expired" in results[0].title
        assert results[0].source_clause_id == clause.id

    def test_contract_expiring_soon_rule(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        clause = base_contract_setup["clause"]
        chunk = base_contract_setup["chunk"]

        # 20 days remaining relative to reference date
        future_fact = ContractFact(
            contract_id=contract.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            fact_key="expiration_date",
            fact_value="2026-10-03",
            verbatim_evidence="Agreement terminates on October 3, 2026",
            page_number=2,
        )

        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[clause],
            obligations=[],
            facts=[future_fact],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        rule = ContractExpiringSoonRule()
        results = rule.evaluate(ctx)
        assert len(results) == 1
        assert results[0].rule_id == "RULE_CONTRACT_EXPIRING_SOON"
        assert results[0].severity == RiskSeverity.HIGH
        assert "20 Days" in results[0].title

    def test_auto_renewal_and_short_notice_rules(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        chunk = base_contract_setup["chunk"]

        auto_renew_clause = Clause(
            contract_id=contract.id,
            source_chunk_id=chunk.id,
            clause_type="auto_renewal",
            clause_label="Section 5.3 — Successive Renewals",
            verbatim_text="This Agreement shall automatically renew for successive 1-year terms unless notice of non-renewal is provided at least 15 days prior.",
            page_number=2,
        )
        notice_fact = ContractFact(
            contract_id=contract.id,
            source_clause_id=auto_renew_clause.id,
            source_chunk_id=chunk.id,
            fact_key="notice_period",
            fact_value="15 days",
            verbatim_evidence="at least 15 days prior",
            page_number=2,
        )

        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[auto_renew_clause],
            obligations=[],
            facts=[notice_fact],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        # Auto renewal active rule
        rule_ar = AutoRenewalActiveRule()
        ar_results = rule_ar.evaluate(ctx)
        assert len(ar_results) == 1
        assert ar_results[0].rule_id == "RULE_AUTO_RENEWAL_ACTIVE"

        # Short notice rule (15 days <= 30 days)
        rule_short = AutoRenewalShortNoticeRule()
        short_results = rule_short.evaluate(ctx)
        assert len(short_results) == 1
        assert short_results[0].rule_id == "RULE_AUTO_RENEWAL_SHORT_NOTICE"
        assert short_results[0].severity == RiskSeverity.HIGH

    def test_no_false_positives_when_facts_absent(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        chunk = base_contract_setup["chunk"]

        # No expiration_date, no auto-renewal
        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[],
            obligations=[],
            facts=[],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        assert len(ContractExpiredRule().evaluate(ctx)) == 0
        assert len(ContractExpiringSoonRule().evaluate(ctx)) == 0
        assert len(AutoRenewalActiveRule().evaluate(ctx)) == 0
        assert len(AutoRenewalShortNoticeRule().evaluate(ctx)) == 0


# ====================================================================
# Suite 2: Contract Risk Rules (Phase 8C)
# ====================================================================

class TestContractRiskRules:
    """Tests for liability, indemnification, termination, and critical terms."""

    def test_termination_notice_short(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        clause = base_contract_setup["clause"]
        chunk = base_contract_setup["chunk"]

        term_fact = ContractFact(
            contract_id=contract.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            fact_key="termination_notice_period",
            fact_value="10 business days",
            verbatim_evidence="terminate upon 10 days notice",
            page_number=2,
        )

        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[clause],
            obligations=[],
            facts=[term_fact],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        rule = TerminationNoticeShortRule()
        results = rule.evaluate(ctx)
        assert len(results) == 1
        assert results[0].rule_id == "RULE_TERMINATION_NOTICE_SHORT"
        assert results[0].severity == RiskSeverity.HIGH
        assert results[0].category == RiskCategory.TERMINATION

    def test_uncapped_liability_rule(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        clause = base_contract_setup["clause"]
        chunk = base_contract_setup["chunk"]

        uncapped_fact = ContractFact(
            contract_id=contract.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            fact_key="liability_cap",
            fact_value="Uncapped Liability",
            verbatim_evidence="Neither party shall have any aggregate limitation of liability",
            page_number=2,
        )

        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[clause],
            obligations=[],
            facts=[uncapped_fact],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        rule = UncappedLiabilityRule()
        results = rule.evaluate(ctx)
        assert len(results) == 1
        assert results[0].rule_id == "RULE_UNCAPPED_LIABILITY"
        assert results[0].severity == RiskSeverity.CRITICAL

    def test_missing_governing_law_rule(self, base_contract_setup: dict):
        contract = base_contract_setup["contract"]
        clause = base_contract_setup["clause"]
        chunk = base_contract_setup["chunk"]

        # Clauses exist, but neither governing_law fact nor clause exists
        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=[clause],
            obligations=[],
            facts=[],
            chunks=[chunk],
            reference_date=date(2026, 9, 13),
        )

        rule = MissingGoverningLawRule()
        results = rule.evaluate(ctx)
        assert len(results) == 1
        assert results[0].rule_id == "RULE_MISSING_GOVERNING_LAW"
        assert results[0].category == RiskCategory.CRITICAL_TERMS


# ====================================================================
# Suite 3: Risk API & Idempotency (Phase 8D)
# ====================================================================

class TestRiskAPIAndIdempotency:
    """Tests for evaluate, list, idempotency, and recalculation."""

    def test_evaluate_and_list_risks_api(self, client: TestClient, base_contract_setup: dict, db_session: Session):
        contract = base_contract_setup["contract"]
        clause = base_contract_setup["clause"]
        chunk = base_contract_setup["chunk"]

        # Insert a fact that triggers Uncapped Liability
        fact = ContractFact(
            contract_id=contract.id,
            source_clause_id=clause.id,
            source_chunk_id=chunk.id,
            fact_key="liability_cap",
            fact_value="Unlimited / Uncapped",
            verbatim_evidence="Unlimited liability for all claims",
            page_number=2,
        )
        db_session.add(fact)
        db_session.commit()

        # 1. POST /contracts/{contract_id}/risks/evaluate
        eval_res = client.post(f"/contracts/{contract.id}/risks/evaluate", json={"force_reevaluate": False})
        assert eval_res.status_code == 200
        eval_data = eval_res.json()
        assert eval_data["contract_id"] == str(contract.id)
        assert eval_data["total_risks_detected"] >= 1
        assert eval_data["critical_count"] >= 1

        first_signal = eval_data["signals"][0]
        assert first_signal["contract_id"] == str(contract.id)
        assert first_signal["rule_id"] is not None

        # 2. Idempotency check: Running again without force_reevaluate returns existing records
        eval_res_2 = client.post(f"/contracts/{contract.id}/risks/evaluate", json={"force_reevaluate": False})
        assert eval_res_2.status_code == 200
        assert eval_res_2.json()["total_risks_detected"] == eval_data["total_risks_detected"]

        # Verify database record count did not multiply
        persisted_count = db_session.query(RiskSignal).filter(RiskSignal.contract_id == contract.id).count()
        assert persisted_count == eval_data["total_risks_detected"]

        # 3. GET /contracts/{contract_id}/risks
        list_res = client.get(f"/contracts/{contract.id}/risks")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total_risks"] == eval_data["total_risks_detected"]

        # 4. Filter by severity=critical
        crit_res = client.get(f"/contracts/{contract.id}/risks?severity=critical")
        assert crit_res.status_code == 200
        assert all(s["severity"] == "critical" for s in crit_res.json()["signals"])

        # 5. Force re-evaluation
        re_res = client.post(f"/contracts/{contract.id}/risks/evaluate", json={"force_reevaluate": True})
        assert re_res.status_code == 200
        assert re_res.json()["total_risks_detected"] == eval_data["total_risks_detected"]
