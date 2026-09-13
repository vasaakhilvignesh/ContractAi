"""
ContractIQ — Risk Service Layer (Phase 8D)

Orchestrates deterministic risk evaluation, persistence, lineage preservation,
and query listing for RiskSignals.

Guarantees:
  - Strict determinism (no LLM decision-making for severity or triggers).
  - Idempotency: Running evaluation multiple times yields identical persisted results;
    if signals already exist, returns them unless force_reevaluate=True.
  - Complete 6-tier lineage:
      RiskSignal → Rule → ContractFact/Clause/Obligation → Chunk → Page → Contract.
"""

from datetime import date
import logging
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.models.risk_signal import RiskSignal
from app.schemas.risk import (
    RiskEvaluationResponse,
    RiskSeverity,
    RiskSignalListResponse,
    RiskSignalResponse,
)
from app.services.risk_engine import (
    BaseRiskRule,
    ContractEvaluationContext,
    STANDARD_RISK_RULES,
    evaluate_contract_rules,
)

logger = logging.getLogger(__name__)


# ====================================================================
# Exceptions
# ====================================================================

class RiskServiceError(Exception):
    """Base exception for risk service operations."""
    pass


class ContractNotFoundError(RiskServiceError):
    """Raised when the target contract is not found."""
    pass


class RiskEvaluationError(RiskServiceError):
    """Raised when risk evaluation fails."""
    pass


# ====================================================================
# Risk Evaluation & Persistence
# ====================================================================

def evaluate_and_persist_contract_risks(
    db: Session,
    contract_id: uuid.UUID,
    force_reevaluate: bool = False,
    reference_date: Optional[date] = None,
    rules: Optional[list[BaseRiskRule]] = None,
) -> RiskEvaluationResponse:
    """
    Deterministically evaluates all registered risk rules on a contract and persists
    the resulting RiskSignal records in the database.

    Idempotent:
      - If signals already exist and force_reevaluate=False, returns existing signals.
      - If force_reevaluate=True, deletes existing signals for this contract and recalculates.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # Check for existing risk signals (idempotency check)
    existing_signals = (
        db.query(RiskSignal)
        .filter(RiskSignal.contract_id == contract_id)
        .order_by(RiskSignal.created_at.asc())
        .all()
    )

    if existing_signals and not force_reevaluate:
        logger.info(
            "Returning %d existing risk signals for contract %s (idempotent)",
            len(existing_signals),
            contract_id,
        )
        return _build_evaluation_response(contract_id, existing_signals, len(rules or STANDARD_RISK_RULES))

    try:
        # If force re-evaluating, clear previous signals
        if force_reevaluate and existing_signals:
            db.query(RiskSignal).filter(RiskSignal.contract_id == contract_id).delete()
            db.commit()

        # Gather structured data context
        clauses = (
            db.query(Clause)
            .filter(Clause.contract_id == contract_id)
            .order_by(Clause.page_number.asc(), Clause.created_at.asc())
            .all()
        )
        obligations = (
            db.query(Obligation)
            .filter(Obligation.contract_id == contract_id)
            .order_by(Obligation.page_number.asc(), Obligation.created_at.asc())
            .all()
        )
        facts = (
            db.query(ContractFact)
            .filter(ContractFact.contract_id == contract_id)
            .order_by(ContractFact.page_number.asc(), ContractFact.created_at.asc())
            .all()
        )
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.contract_id == contract_id)
            .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_index.asc())
            .all()
        )

        today = reference_date or date.today()
        ctx = ContractEvaluationContext(
            contract=contract,
            clauses=clauses,
            obligations=obligations,
            facts=facts,
            chunks=chunks,
            reference_date=today,
        )

        active_rules = rules if rules is not None else STANDARD_RISK_RULES
        rule_outputs = evaluate_contract_rules(ctx, rules=active_rules)

        persisted_signals: list[RiskSignal] = []
        for out in rule_outputs:
            signal = RiskSignal(
                contract_id=contract_id,
                rule_id=out.rule_id,
                rule_description=out.rule_description,
                severity=out.severity.value if hasattr(out.severity, "value") else str(out.severity),
                category=out.category.value if hasattr(out.category, "value") else str(out.category),
                title=out.title,
                triggered_fact=out.triggered_fact,
                verbatim_evidence=out.verbatim_evidence,
                page_number=out.page_number,
                recommended_action=out.recommended_action,
                source_clause_id=out.source_clause_id,
                source_chunk_id=out.source_chunk_id,
            )
            db.add(signal)
            persisted_signals.append(signal)

        db.commit()

        for s in persisted_signals:
            db.refresh(s)

        return _build_evaluation_response(contract_id, persisted_signals, len(active_rules))

    except Exception as exc:
        db.rollback()
        logger.error("Failed evaluating risks for contract %s: %s", contract_id, exc)
        if isinstance(exc, RiskServiceError):
            raise
        raise RiskEvaluationError(f"Risk evaluation failed for contract '{contract_id}': {exc}") from exc


def list_contract_risk_signals(
    db: Session,
    contract_id: uuid.UUID,
    severity: Optional[str] = None,
    category: Optional[str] = None,
) -> RiskSignalListResponse:
    """
    Lists persisted RiskSignal records for a contract with optional severity and category filtering.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    query = db.query(RiskSignal).filter(RiskSignal.contract_id == contract_id)

    if severity:
        query = query.filter(RiskSignal.severity == severity.strip().lower())

    if category:
        query = query.filter(RiskSignal.category == category.strip().lower())

    signals = (
        query.order_by(
            RiskSignal.severity.asc(),
            RiskSignal.page_number.asc().nulls_last(),
            RiskSignal.created_at.asc(),
        )
        .all()
    )

    signal_responses = [RiskSignalResponse.model_validate(s) for s in signals]

    # Calculate counts
    critical_count = sum(1 for s in signals if s.severity == RiskSeverity.CRITICAL.value)
    high_count = sum(1 for s in signals if s.severity == RiskSeverity.HIGH.value)
    medium_count = sum(1 for s in signals if s.severity == RiskSeverity.MEDIUM.value)
    low_count = sum(1 for s in signals if s.severity == RiskSeverity.LOW.value)

    return RiskSignalListResponse(
        contract_id=contract_id,
        total_risks=len(signal_responses),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        signals=signal_responses,
    )


# ====================================================================
# Helper
# ====================================================================

def _build_evaluation_response(
    contract_id: uuid.UUID,
    signals: list[RiskSignal],
    total_rules: int,
) -> RiskEvaluationResponse:
    signal_responses = [RiskSignalResponse.model_validate(s) for s in signals]
    critical_count = sum(1 for s in signals if s.severity == RiskSeverity.CRITICAL.value)
    high_count = sum(1 for s in signals if s.severity == RiskSeverity.HIGH.value)
    medium_count = sum(1 for s in signals if s.severity == RiskSeverity.MEDIUM.value)
    low_count = sum(1 for s in signals if s.severity == RiskSeverity.LOW.value)

    return RiskEvaluationResponse(
        contract_id=contract_id,
        total_rules_evaluated=total_rules,
        total_risks_detected=len(signals),
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        signals=signal_responses,
    )
