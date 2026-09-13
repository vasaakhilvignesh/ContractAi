"""
ContractIQ — Clause Extraction Service (Phase 6B)

Extracts structured contractual clauses from processed DocumentChunks using
the Phase 6A StructuredLLMProvider infrastructure.

Key Guarantees:
  - Deterministic chunk ordering (chunk_index.asc()).
  - Strict evidence lineage preservation: clause → chunk → page → contract.
  - Idempotent execution (returns existing clauses unless force_reextract=True).
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
from app.models.document_chunk import DocumentChunk
from app.schemas.clause import (
    ChunkClauseExtractionResult,
    ClauseResponse,
    ContractClauseExtractionResponse,
    ContractClauseListResponse,
    ExtractedClauseLLM,
)
from app.services.structured_output_factory import get_structured_llm_provider
from app.services.structured_output_provider import StructuredLLMProvider
from app.services.structured_output_validator import StructuredOutputError

logger = logging.getLogger(__name__)

CLAUSE_EXTRACTION_SYSTEM_PROMPT = (
    "You are an expert legal contract analyst. Extract operative contractual clauses "
    "from the provided contract text chunk. Identify the clause category (termination, liability, "
    "indemnification, auto_renewal, confidentiality, payment, governing_law, dispute_resolution, "
    "intellectual_property, warranty, data_privacy, or other), the section heading or clause label if present, "
    "and the exact verbatim text of each clause. If the text does not contain any operative clauses, "
    "return an empty list with has_clauses=false."
)


# ====================================================================
# Exceptions
# ====================================================================

class ClauseExtractionError(Exception):
    """Base exception for all clause extraction errors."""
    pass


class ContractNotFoundError(ClauseExtractionError):
    """Raised when the specified contract is not found in the database."""
    pass


class NoChunksFoundError(ClauseExtractionError):
    """Raised when the contract has no document chunks to process."""
    pass


class ExtractionProviderError(ClauseExtractionError):
    """Raised when LLM extraction fails."""
    pass


# ====================================================================
# Chunk Extraction Function
# ====================================================================

async def extract_clauses_from_chunk(
    chunk: DocumentChunk,
    provider: StructuredLLMProvider,
) -> list[ExtractedClauseLLM]:
    """
    Extracts structured legal clauses from a single DocumentChunk.

    Args:
        chunk: The DocumentChunk database model instance.
        provider: An implementation of StructuredLLMProvider.

    Returns:
        A list of ExtractedClauseLLM items conforming to the schema.
    """
    prompt = (
        f"Document Context:\n"
        f"- Page Number: {chunk.page_number}\n"
        f"- Section Header: {chunk.section_header or 'N/A'}\n\n"
        f"Contract Text Chunk (Chunk Index {chunk.chunk_index}):\n"
        f'"""\n{chunk.text}\n"""\n\n'
        f"Extract all operative legal clauses found in this text chunk according to the required schema."
    )

    try:
        result: ChunkClauseExtractionResult = await provider.generate_structured(
            prompt=prompt,
            schema=ChunkClauseExtractionResult,
            system_instruction=CLAUSE_EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,
        )
        return result.clauses
    except StructuredOutputError as exc:
        logger.warning(
            "Structured extraction failed on chunk %s (page %s): %s",
            chunk.id,
            chunk.page_number,
            exc,
        )
        return []


# ====================================================================
# Contract Extraction Orchestration
# ====================================================================

async def extract_contract_clauses(
    db: Session,
    contract_id: uuid.UUID,
    force_reextract: bool = False,
    provider: StructuredLLMProvider | None = None,
) -> ContractClauseExtractionResponse:
    """
    Extracts and persists structured clauses across all chunks of a contract.

    Args:
        db: Active SQLAlchemy database session.
        contract_id: UUID of the target contract.
        force_reextract: If True, clears existing clauses and forces fresh extraction.
        provider: Optional StructuredLLMProvider instance for dependency injection.

    Returns:
        ContractClauseExtractionResponse with extraction metrics and clause details.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # Idempotency check: return existing clauses unless force_reextract is True
    existing_clauses = (
        db.query(Clause)
        .filter(Clause.contract_id == contract_id)
        .order_by(Clause.page_number.asc(), Clause.created_at.asc())
        .all()
    )

    if existing_clauses and not force_reextract:
        logger.info(
            "Contract %s already has %d extracted clauses. Returning existing (idempotent).",
            contract_id,
            len(existing_clauses),
        )
        counts = Counter(c.clause_type for c in existing_clauses)
        clause_responses = [ClauseResponse.model_validate(c) for c in existing_clauses]
        chunks_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.contract_id == contract_id)
            .count()
        )
        return ContractClauseExtractionResponse(
            contract_id=contract_id,
            total_chunks_processed=chunks_count,
            total_clauses_extracted=len(clause_responses),
            clauses_by_type=dict(counts),
            clauses=clause_responses,
        )

    # Load chunks in strict deterministic order
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.contract_id == contract_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )

    if not chunks:
        raise NoChunksFoundError(
            f"Contract '{contract_id}' has no document chunks. "
            f"Please chunk the contract before running clause extraction."
        )

    llm_provider = provider or get_structured_llm_provider()

    try:
        if force_reextract and existing_clauses:
            db.query(Clause).filter(Clause.contract_id == contract_id).delete(
                synchronize_session=False
            )
            db.flush()

        persisted_clauses: list[Clause] = []

        for chunk in chunks:
            extracted_items = await extract_clauses_from_chunk(chunk, llm_provider)

            for item in extracted_items:
                clause_type_val = (
                    item.clause_type.value
                    if hasattr(item.clause_type, "value")
                    else str(item.clause_type).lower()
                )
                clause_label_val = item.clause_label or chunk.section_header or None

                clause = Clause(
                    id=uuid.uuid4(),
                    contract_id=contract_id,
                    source_chunk_id=chunk.id,
                    clause_type=clause_type_val,
                    clause_label=clause_label_val,
                    verbatim_text=item.verbatim_text,
                    page_number=chunk.page_number,
                    extraction_confidence=item.confidence,
                    is_reviewed=False,
                )
                db.add(clause)
                persisted_clauses.append(clause)

        db.commit()

        # Re-query persisted clauses to obtain server-generated timestamps
        all_clauses = (
            db.query(Clause)
            .filter(Clause.contract_id == contract_id)
            .order_by(Clause.page_number.asc(), Clause.created_at.asc())
            .all()
        )

        counts = Counter(c.clause_type for c in all_clauses)
        clause_responses = [ClauseResponse.model_validate(c) for c in all_clauses]

        return ContractClauseExtractionResponse(
            contract_id=contract_id,
            total_chunks_processed=len(chunks),
            total_clauses_extracted=len(clause_responses),
            clauses_by_type=dict(counts),
            clauses=clause_responses,
        )

    except Exception as exc:
        db.rollback()
        logger.error(
            "Failed during clause extraction for contract %s: %s",
            contract_id,
            exc,
        )
        if isinstance(exc, ClauseExtractionError):
            raise
        raise ClauseExtractionError(
            f"Clause extraction failed for contract '{contract_id}': {str(exc)}"
        ) from exc


# ====================================================================
# Clause Querying / Listing
# ====================================================================

def list_contract_clauses(
    db: Session,
    contract_id: uuid.UUID,
    clause_type: Optional[str] = None,
) -> ContractClauseListResponse:
    """
    Lists persisted clauses for a contract, with optional clause_type filtering.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    query = db.query(Clause).filter(Clause.contract_id == contract_id)

    if clause_type:
        query = query.filter(Clause.clause_type == clause_type.strip().lower())

    clauses = query.order_by(Clause.page_number.asc(), Clause.created_at.asc()).all()
    clause_responses = [ClauseResponse.model_validate(c) for c in clauses]

    return ContractClauseListResponse(
        contract_id=contract_id,
        total_clauses=len(clause_responses),
        clauses=clause_responses,
    )
