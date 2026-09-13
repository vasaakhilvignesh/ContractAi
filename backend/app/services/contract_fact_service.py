"""
ContractIQ — Contract Fact Extraction Service (Phase 6D)

Extracts structured contract-level facts from previously extracted Clauses using
the Phase 6A StructuredLLMProvider infrastructure.

Key Guarantees:
  - Source evidence traceability: fact → source clause → chunk → page → contract.
  - Deterministic clause ordering (page_number.asc(), created_at.asc(), id.asc()).
  - Idempotent execution (returns existing facts unless force_reextract=True).
  - Atomic database transactions with rollback on failure.
  - Robust handling of LLM outputs via Phase 6A structured output validation.
  - Strict absence of invented/hallucinated values when facts are not stated.
"""

from collections import Counter
import logging
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.schemas.contract_fact import (
    ClauseFactExtractionResult,
    ContractFactExtractionResponse,
    ContractFactListResponse,
    ContractFactResponse,
    ExtractedFactLLM,
)
from app.services.structured_output_factory import get_structured_llm_provider
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import StructuredOutputError

logger = logging.getLogger(__name__)

CONTRACT_FACT_EXTRACTION_SYSTEM_PROMPT = (
    "You are an expert legal contract analyst. Extract clearly stated, operative contract-level facts "
    "from the provided clause text. Examples of contract-level facts include: "
    "effective_date, expiration_date, contract_value, payment_terms, currency, parties, "
    "governing_law, notice_period, renewal_term, termination_notice_period, liability_cap, "
    "indemnification_cap, dispute_forum, confidentiality_period, and other. "
    "For each fact identified: "
    "1) fact_key: the standard identifier (e.g. 'effective_date', 'governing_law', 'notice_period', 'parties', etc.), "
    "2) fact_value: the clean, normalized textual value (e.g. '2025-01-01', 'State of Delaware', '30 days', 'USD 1,200,000'), "
    "3) fact_value_json: optional JSON-formatted string for complex or multi-valued facts (e.g. JSON array of parties), "
    "4) verbatim_evidence: the exact excerpt from the clause text that proves this fact, "
    "5) confidence: confidence score from 0.0 to 1.0. "
    "CRITICAL: Do NOT invent, assume, or hallucinate facts that are not explicitly stated in the text. "
    "If a clause does not clearly state any contract-level facts, return an empty list with has_facts=false."
)


# ====================================================================
# Exceptions
# ====================================================================

class ContractFactExtractionError(Exception):
    """Base exception for all contract fact extraction errors."""
    pass


class ContractNotFoundError(ContractFactExtractionError):
    """Raised when the specified contract is not found in the database."""
    pass


class NoClausesFoundError(ContractFactExtractionError):
    """Raised when the contract has no clauses from which to extract facts."""
    pass


class ExtractionProviderError(ContractFactExtractionError):
    """Raised when LLM extraction fails."""
    pass


# ====================================================================
# Clause-Level Fact Extraction
# ====================================================================

async def extract_facts_from_clause(
    clause: Clause,
    provider: StructuredLLMProvider,
) -> list[ExtractedFactLLM]:
    """
    Extracts structured contract-level facts from a single Clause record.

    Args:
        clause: The Clause database model instance.
        provider: An implementation of StructuredLLMProvider.

    Returns:
        A list of ExtractedFactLLM items conforming to the schema.
    """
    prompt = (
        f"Clause Metadata:\n"
        f"- Clause ID: {clause.id}\n"
        f"- Clause Type: {clause.clause_type}\n"
        f"- Clause Label: {clause.clause_label or 'N/A'}\n"
        f"- Source Page: {clause.page_number or 'N/A'}\n\n"
        f"Clause Operative Text:\n"
        f'"""\n{clause.verbatim_text}\n"""\n\n'
        f"Extract all operative, clearly stated contract-level facts found in this clause according to the required schema."
    )

    try:
        result: ClauseFactExtractionResult = await provider.generate_structured(
            prompt=prompt,
            schema=ClauseFactExtractionResult,
            system_instruction=CONTRACT_FACT_EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,
        )
        return result.facts
    except StructuredOutputError as exc:
        logger.warning(
            "Structured fact extraction failed on clause %s (type %s, page %s): %s",
            clause.id,
            clause.clause_type,
            clause.page_number,
            exc,
        )
        return []


# ====================================================================
# Contract Fact Extraction Orchestration
# ====================================================================

async def extract_contract_facts(
    db: Session,
    contract_id: uuid.UUID,
    force_reextract: bool = False,
    provider: StructuredLLMProvider | None = None,
) -> ContractFactExtractionResponse:
    """
    Extracts and persists structured contract-level facts across all clauses of a contract.

    Preserves complete evidence lineage:
        fact → source clause → chunk → page → contract

    Args:
        db: Active SQLAlchemy database session.
        contract_id: UUID of the target contract.
        force_reextract: If True, clears existing facts and forces fresh extraction.
        provider: Optional StructuredLLMProvider instance for dependency injection.

    Returns:
        ContractFactExtractionResponse with extraction metrics and fact details.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # Idempotency check: return existing facts unless force_reextract is True
    existing_facts = (
        db.query(ContractFact)
        .filter(ContractFact.contract_id == contract_id)
        .order_by(ContractFact.page_number.asc(), ContractFact.created_at.asc())
        .all()
    )

    if existing_facts and not force_reextract:
        logger.info(
            "Contract %s already has %d extracted facts. Returning existing (idempotent).",
            contract_id,
            len(existing_facts),
        )
        key_counts = Counter(f.fact_key for f in existing_facts)
        fact_responses = [ContractFactResponse.model_validate(f) for f in existing_facts]
        clauses_count = (
            db.query(Clause)
            .filter(Clause.contract_id == contract_id)
            .count()
        )
        return ContractFactExtractionResponse(
            contract_id=contract_id,
            total_clauses_analyzed=clauses_count,
            total_facts_extracted=len(fact_responses),
            facts_by_key=dict(key_counts),
            facts=fact_responses,
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
            f"Please run clause extraction before extracting contract facts."
        )

    llm_provider = provider or get_structured_llm_provider()

    try:
        if force_reextract and existing_facts:
            db.query(ContractFact).filter(ContractFact.contract_id == contract_id).delete(
                synchronize_session=False
            )
            db.flush()

        persisted_facts: list[ContractFact] = []

        for clause in clauses:
            extracted_items = await extract_facts_from_clause(clause, llm_provider)

            for item in extracted_items:
                fact_key_val = (
                    item.fact_key.value
                    if hasattr(item.fact_key, "value")
                    else str(item.fact_key).lower()
                )

                # Preserve complete lineage: fact → source clause → chunk → page → contract
                fact = ContractFact(
                    id=uuid.uuid4(),
                    contract_id=contract_id,
                    source_clause_id=clause.id,
                    source_chunk_id=clause.source_chunk_id,
                    page_number=clause.page_number,
                    fact_key=fact_key_val,
                    fact_value=item.fact_value,
                    fact_value_json=item.fact_value_json,
                    verbatim_evidence=item.verbatim_evidence or clause.verbatim_text,
                    confidence=item.confidence,
                )
                db.add(fact)
                persisted_facts.append(fact)

        db.commit()

        # Re-query persisted facts to obtain server-generated timestamps
        all_facts = (
            db.query(ContractFact)
            .filter(ContractFact.contract_id == contract_id)
            .order_by(ContractFact.page_number.asc(), ContractFact.created_at.asc())
            .all()
        )

        key_counts = Counter(f.fact_key for f in all_facts)
        fact_responses = [ContractFactResponse.model_validate(f) for f in all_facts]

        return ContractFactExtractionResponse(
            contract_id=contract_id,
            total_clauses_analyzed=len(clauses),
            total_facts_extracted=len(fact_responses),
            facts_by_key=dict(key_counts),
            facts=fact_responses,
        )

    except Exception as exc:
        db.rollback()
        logger.error(
            "Failed during fact extraction for contract %s: %s",
            contract_id,
            exc,
        )
        if isinstance(exc, ContractFactExtractionError):
            raise
        raise ContractFactExtractionError(
            f"Contract fact extraction failed for contract '{contract_id}': {str(exc)}"
        ) from exc


# ====================================================================
# Fact Querying / Listing
# ====================================================================

def list_contract_facts(
    db: Session,
    contract_id: uuid.UUID,
    fact_key: Optional[str] = None,
) -> ContractFactListResponse:
    """
    Lists persisted contract facts for a contract with optional fact_key filtering.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    query = db.query(ContractFact).filter(ContractFact.contract_id == contract_id)

    if fact_key:
        query = query.filter(
            ContractFact.fact_key == fact_key.strip().lower()
        )

    facts = query.order_by(ContractFact.page_number.asc(), ContractFact.created_at.asc()).all()
    fact_responses = [ContractFactResponse.model_validate(f) for f in facts]

    return ContractFactListResponse(
        contract_id=contract_id,
        total_facts=len(fact_responses),
        facts=fact_responses,
    )
