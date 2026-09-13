"""
ContractIQ — Obligation Extraction Service (Phase 6C)

Extracts structured contractual obligations from previously extracted Clauses using
the Phase 6A StructuredLLMProvider infrastructure.

Key Guarantees:
  - Source evidence traceability: obligation → clause → chunk → page → contract.
  - Deterministic clause ordering (page_number.asc(), created_at.asc(), id.asc()).
  - Idempotent execution (returns existing obligations unless force_reextract=True).
  - Atomic database transactions with rollback on failure.
  - Robust handling of LLM outputs via Phase 6A structured output validation.
"""

from collections import Counter
import logging
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.clause import Clause
from app.models.contract import Contract
from app.models.obligation import Obligation
from app.schemas.obligation import (
    ClauseObligationExtractionResult,
    ContractObligationExtractionResponse,
    ContractObligationListResponse,
    ExtractedObligationLLM,
    ObligationResponse,
)
from app.services.structured_output_factory import get_structured_llm_provider
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import StructuredOutputError

logger = logging.getLogger(__name__)

OBLIGATION_EXTRACTION_SYSTEM_PROMPT = (
    "You are an expert legal contract analyst. Extract all operative, legally binding contractual "
    "obligations from the provided clause text. For each obligation identify: "
    "1) A concise title summarizing the obligation, "
    "2) A detailed description of what action, duty, or constraint must be performed, "
    "3) The responsible party required to fulfill it (e.g., 'Vendor', 'Customer', 'Both Parties', or specific entity), "
    "4) The obligation type (payment, delivery, reporting, notice, confidentiality, compliance, audit, insurance, renewal, termination, or other), "
    "5) Any due date, deadline, or timing trigger if defined in the text, "
    "6) The recurrence frequency if recurring (e.g., 'Monthly', 'Quarterly', 'Annually', 'On-demand', 'One-time'), "
    "7) Whether it is a recurring obligation (boolean), "
    "8) The exact verbatim excerpt from the clause text establishing the obligation, "
    "9) Confidence score (0.0 to 1.0). "
    "If the clause contains no operative obligations (e.g., recitals, definitions, general statements), "
    "return an empty list with has_obligations=false."
)


# ====================================================================
# Exceptions
# ====================================================================

class ObligationExtractionError(Exception):
    """Base exception for all obligation extraction errors."""
    pass


class ContractNotFoundError(ObligationExtractionError):
    """Raised when the specified contract is not found in the database."""
    pass


class NoClausesFoundError(ObligationExtractionError):
    """Raised when the contract has no clauses from which to extract obligations."""
    pass


class ExtractionProviderError(ObligationExtractionError):
    """Raised when LLM extraction fails."""
    pass


# ====================================================================
# Clause-Level Obligation Extraction
# ====================================================================

async def extract_obligations_from_clause(
    clause: Clause,
    provider: StructuredLLMProvider,
) -> list[ExtractedObligationLLM]:
    """
    Extracts structured obligations from a single Clause record.

    Args:
        clause: The Clause database model instance.
        provider: An implementation of StructuredLLMProvider.

    Returns:
        A list of ExtractedObligationLLM items conforming to the schema.
    """
    prompt = (
        f"Clause Metadata:\n"
        f"- Clause ID: {clause.id}\n"
        f"- Clause Type: {clause.clause_type}\n"
        f"- Clause Label: {clause.clause_label or 'N/A'}\n"
        f"- Source Page: {clause.page_number or 'N/A'}\n\n"
        f"Clause Operative Text:\n"
        f'"""\n{clause.verbatim_text}\n"""\n\n'
        f"Extract all operative contractual obligations found in this clause according to the required schema."
    )

    try:
        result: ClauseObligationExtractionResult = await provider.generate_structured(
            prompt=prompt,
            schema=ClauseObligationExtractionResult,
            system_instruction=OBLIGATION_EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,
        )
        return result.obligations
    except StructuredOutputError as exc:
        logger.warning(
            "Structured obligation extraction failed on clause %s (type %s, page %s): %s",
            clause.id,
            clause.clause_type,
            clause.page_number,
            exc,
        )
        return []


# ====================================================================
# Contract Obligation Extraction Orchestration
# ====================================================================

async def extract_contract_obligations(
    db: Session,
    contract_id: uuid.UUID,
    force_reextract: bool = False,
    provider: StructuredLLMProvider | None = None,
) -> ContractObligationExtractionResponse:
    """
    Extracts and persists structured obligations across all clauses of a contract.

    Preserves complete evidence lineage:
        obligation → clause → chunk → page → contract

    Args:
        db: Active SQLAlchemy database session.
        contract_id: UUID of the target contract.
        force_reextract: If True, clears existing obligations and forces fresh extraction.
        provider: Optional StructuredLLMProvider instance for dependency injection.

    Returns:
        ContractObligationExtractionResponse with extraction metrics and obligation details.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # Idempotency check: return existing obligations unless force_reextract is True
    existing_obligations = (
        db.query(Obligation)
        .filter(Obligation.contract_id == contract_id)
        .order_by(Obligation.page_number.asc(), Obligation.created_at.asc())
        .all()
    )

    if existing_obligations and not force_reextract:
        logger.info(
            "Contract %s already has %d extracted obligations. Returning existing (idempotent).",
            contract_id,
            len(existing_obligations),
        )
        party_counts = Counter(o.responsible_party or "Unknown" for o in existing_obligations)
        type_counts = Counter(o.obligation_type or "other" for o in existing_obligations)
        obligation_responses = [ObligationResponse.model_validate(o) for o in existing_obligations]
        clauses_count = (
            db.query(Clause)
            .filter(Clause.contract_id == contract_id)
            .count()
        )
        return ContractObligationExtractionResponse(
            contract_id=contract_id,
            total_clauses_analyzed=clauses_count,
            total_obligations_extracted=len(obligation_responses),
            obligations_by_party=dict(party_counts),
            obligations_by_type=dict(type_counts),
            obligations=obligation_responses,
        )

    # Load clauses in strict deterministic order
    clauses = (
        db.query(Clause)
        .filter(Clause.contract_id == contract_id)
        .order_by(Clause.page_number.asc(), Clause.created_at.asc(), Clause.id.asc())
        .all()
    )

    if not clauses:
        raise NoClausesFoundError(
            f"Contract '{contract_id}' has no extracted clauses. "
            f"Please run clause extraction before extracting obligations."
        )

    llm_provider = provider or get_structured_llm_provider()

    try:
        if force_reextract and existing_obligations:
            db.query(Obligation).filter(Obligation.contract_id == contract_id).delete(
                synchronize_session=False
            )
            db.flush()

        persisted_obligations: list[Obligation] = []

        for clause in clauses:
            extracted_items = await extract_obligations_from_clause(clause, llm_provider)

            for item in extracted_items:
                obligation_type_val = (
                    item.obligation_type.value
                    if hasattr(item.obligation_type, "value")
                    else str(item.obligation_type).lower()
                )

                # Preserve complete lineage: obligation → clause → chunk → page → contract
                obligation = Obligation(
                    id=uuid.uuid4(),
                    contract_id=contract_id,
                    source_clause_id=clause.id,
                    source_chunk_id=clause.source_chunk_id,
                    page_number=clause.page_number,
                    title=item.title,
                    description=item.description,
                    responsible_party=item.responsible_party,
                    obligation_type=obligation_type_val,
                    deadline_info=item.due_date_description,
                    frequency=item.frequency,
                    is_recurring=item.is_recurring,
                    verbatim_evidence=item.verbatim_evidence or clause.verbatim_text,
                    extraction_confidence=item.confidence,
                    status="pending",
                    priority="medium",
                )
                db.add(obligation)
                persisted_obligations.append(obligation)

        db.commit()

        # Re-query persisted obligations to obtain server-generated timestamps
        all_obligations = (
            db.query(Obligation)
            .filter(Obligation.contract_id == contract_id)
            .order_by(Obligation.page_number.asc(), Obligation.created_at.asc())
            .all()
        )

        party_counts = Counter(o.responsible_party or "Unknown" for o in all_obligations)
        type_counts = Counter(o.obligation_type or "other" for o in all_obligations)
        obligation_responses = [ObligationResponse.model_validate(o) for o in all_obligations]

        return ContractObligationExtractionResponse(
            contract_id=contract_id,
            total_clauses_analyzed=len(clauses),
            total_obligations_extracted=len(obligation_responses),
            obligations_by_party=dict(party_counts),
            obligations_by_type=dict(type_counts),
            obligations=obligation_responses,
        )

    except Exception as exc:
        db.rollback()
        logger.error(
            "Failed during obligation extraction for contract %s: %s",
            contract_id,
            exc,
        )
        if isinstance(exc, ObligationExtractionError):
            raise
        raise ObligationExtractionError(
            f"Obligation extraction failed for contract '{contract_id}': {str(exc)}"
        ) from exc


# ====================================================================
# Obligation Querying / Listing
# ====================================================================

def list_contract_obligations(
    db: Session,
    contract_id: uuid.UUID,
    responsible_party: Optional[str] = None,
    obligation_type: Optional[str] = None,
    status: Optional[str] = None,
) -> ContractObligationListResponse:
    """
    Lists persisted obligations for a contract with optional filtering.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    query = db.query(Obligation).filter(Obligation.contract_id == contract_id)

    if responsible_party:
        query = query.filter(
            Obligation.responsible_party.ilike(f"%{responsible_party.strip()}%")
        )

    if obligation_type:
        query = query.filter(
            Obligation.obligation_type == obligation_type.strip().lower()
        )

    if status:
        query = query.filter(
            Obligation.status == status.strip().lower()
        )

    obligations = query.order_by(Obligation.page_number.asc(), Obligation.created_at.asc()).all()
    obligation_responses = [ObligationResponse.model_validate(o) for o in obligations]

    return ContractObligationListResponse(
        contract_id=contract_id,
        total_obligations=len(obligation_responses),
        obligations=obligation_responses,
    )
