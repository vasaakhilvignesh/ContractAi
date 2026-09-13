"""
ContractIQ — Evidence & Validation Service Layer (Phase 7B & Phase 7C)

Provides business logic for:
  - Phase 7B: Querying, filtering, and assembling complete 6-tier evidence lineage:
      evidence → source item → clause → chunk → page → contract.
  - Phase 7C: Deterministic validation of evidence against referenced chunks,
      clauses, pages, character spans, and contract ownership.
"""

import logging
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.evidence import Evidence
from app.models.obligation import Obligation
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceLineage,
    EvidenceLineageListResponse,
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceSourceItemType,
    EvidenceValidationIssue,
    EvidenceValidationSummary,
    SingleEvidenceValidationResult,
)

logger = logging.getLogger(__name__)


# ====================================================================
# Domain Exceptions
# ====================================================================

class EvidenceServiceError(Exception):
    """Base exception for evidence service operations."""
    pass


class ContractNotFoundError(EvidenceServiceError):
    """Raised when a contract is not found in the database."""
    pass


class EvidenceNotFoundError(EvidenceServiceError):
    """Raised when an evidence record is not found."""
    pass


class SourceItemNotFoundError(EvidenceServiceError):
    """Raised when the referenced source item does not exist."""
    pass


class EvidenceValidationError(EvidenceServiceError):
    """Raised when evidence validation fails or invariants are violated."""
    pass


# ====================================================================
# Phase 7B: Evidence Creation & Retrieval Functions
# ====================================================================

def create_evidence(
    db: Session,
    contract_id: uuid.UUID,
    payload: EvidenceCreate,
) -> EvidenceResponse:
    """
    Creates and persists a new Evidence record linked to a contract and source item.
    Enforces contract existence and ownership.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    if payload.contract_id != contract_id:
        raise EvidenceValidationError(
            f"Payload contract_id '{payload.contract_id}' does not match endpoint contract_id '{contract_id}'."
        )

    evidence = Evidence(
        contract_id=contract_id,
        source_item_type=payload.source_item_type.value if hasattr(payload.source_item_type, "value") else str(payload.source_item_type),
        source_item_id=payload.source_item_id,
        source_item_reference=payload.source_item_reference,
        source_clause_id=payload.source_clause_id,
        source_chunk_id=payload.source_chunk_id,
        page_number=payload.page_number,
        source_text=payload.source_text,
        char_start=payload.char_start,
        char_end=payload.char_end,
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return EvidenceResponse.model_validate(evidence)


def get_evidence_by_id(
    db: Session,
    contract_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> EvidenceResponse:
    """
    Retrieves a single evidence record by ID within a contract.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.contract_id == contract_id)
        .first()
    )
    if not evidence:
        raise EvidenceNotFoundError(
            f"Evidence with id '{evidence_id}' not found for contract '{contract_id}'."
        )

    return EvidenceResponse.model_validate(evidence)


def list_contract_evidence(
    db: Session,
    contract_id: uuid.UUID,
    source_item_type: Optional[str] = None,
    source_item_id: Optional[uuid.UUID] = None,
    page_number: Optional[int] = None,
) -> EvidenceListResponse:
    """
    Lists evidence records for a given contract with optional filtering:
      - source_item_type: ('clause' | 'obligation' | 'contract_fact')
      - source_item_id: UUID of specific source item
      - page_number: 1-indexed page number
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    query = db.query(Evidence).filter(Evidence.contract_id == contract_id)

    if source_item_type:
        query = query.filter(Evidence.source_item_type == source_item_type.strip().lower())

    if source_item_id:
        query = query.filter(Evidence.source_item_id == source_item_id)

    if page_number is not None:
        query = query.filter(Evidence.page_number == page_number)

    evidence_items = (
        query.order_by(Evidence.page_number.asc().nulls_last(), Evidence.created_at.asc(), Evidence.id.asc())
        .all()
    )

    return EvidenceListResponse(
        contract_id=contract_id,
        total_evidence=len(evidence_items),
        evidence=[EvidenceResponse.model_validate(e) for e in evidence_items],
    )


def get_evidence_lineage(
    db: Session,
    contract_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> EvidenceLineage:
    """
    Retrieves the complete 6-tier lineage trace for a single evidence record:
    evidence → source item → clause → chunk → page → contract.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.contract_id == contract_id)
        .first()
    )
    if not evidence:
        raise EvidenceNotFoundError(
            f"Evidence with id '{evidence_id}' not found for contract '{contract_id}'."
        )

    # Determine structural lineage references
    resolved_clause_id = evidence.source_clause_id
    resolved_chunk_id = evidence.source_chunk_id
    resolved_page_number = evidence.page_number

    # If missing clause/chunk/page, attempt to trace via source item
    if (not resolved_clause_id or not resolved_chunk_id or resolved_page_number is None):
        if evidence.source_item_type == "clause":
            clause = db.query(Clause).filter(Clause.id == evidence.source_item_id).first()
            if clause:
                resolved_clause_id = resolved_clause_id or clause.id
                resolved_chunk_id = resolved_chunk_id or clause.source_chunk_id
                resolved_page_number = (
                    resolved_page_number if resolved_page_number is not None else clause.page_number
                )
        elif evidence.source_item_type == "obligation":
            obligation = db.query(Obligation).filter(Obligation.id == evidence.source_item_id).first()
            if obligation:
                resolved_clause_id = resolved_clause_id or obligation.source_clause_id
                resolved_chunk_id = resolved_chunk_id or obligation.source_chunk_id
                resolved_page_number = (
                    resolved_page_number if resolved_page_number is not None else obligation.page_number
                )
        elif evidence.source_item_type == "contract_fact":
            fact = db.query(ContractFact).filter(ContractFact.id == evidence.source_item_id).first()
            if fact:
                resolved_clause_id = resolved_clause_id or fact.source_clause_id
                resolved_chunk_id = resolved_chunk_id or fact.source_chunk_id
                resolved_page_number = (
                    resolved_page_number if resolved_page_number is not None else fact.page_number
                )

    # If chunk exists, verify or resolve page number from chunk
    if resolved_chunk_id and resolved_page_number is None:
        chunk = db.query(DocumentChunk).filter(DocumentChunk.id == resolved_chunk_id).first()
        if chunk:
            resolved_page_number = chunk.page_number

    return EvidenceLineage(
        evidence_id=evidence.id,
        source_item_type=evidence.source_item_type,
        source_item_id=evidence.source_item_id,
        source_item_reference=evidence.source_item_reference or f"{evidence.source_item_type}:{evidence.source_item_id}",
        clause_id=resolved_clause_id,
        chunk_id=resolved_chunk_id,
        page_number=resolved_page_number,
        contract_id=contract_id,
        source_text=evidence.source_text,
        char_start=evidence.char_start,
        char_end=evidence.char_end,
        created_at=evidence.created_at,
    )


def list_evidence_lineage(
    db: Session,
    contract_id: uuid.UUID,
    source_item_type: Optional[str] = None,
    source_item_id: Optional[uuid.UUID] = None,
    page_number: Optional[int] = None,
) -> EvidenceLineageListResponse:
    """
    Lists evidence records with complete lineage traces for a contract.
    """
    evidence_list = list_contract_evidence(
        db=db,
        contract_id=contract_id,
        source_item_type=source_item_type,
        source_item_id=source_item_id,
        page_number=page_number,
    )

    lineages = [
        get_evidence_lineage(db=db, contract_id=contract_id, evidence_id=e.id)
        for e in evidence_list.evidence
    ]

    return EvidenceLineageListResponse(
        contract_id=contract_id,
        total_evidence=len(lineages),
        evidence=lineages,
    )


# ====================================================================
# Phase 7C: Deterministic Evidence Validation Service
# ====================================================================

def validate_single_evidence(
    db: Session,
    evidence: Evidence,
) -> SingleEvidenceValidationResult:
    """
    Deterministically validates an individual Evidence record:
      1. Referenced contract existence and ownership.
      2. Referenced source item existence, type match, and contract ownership.
      3. Referenced source clause and chunk existence and contract consistency.
      4. Verbatim source text matching within referenced chunk text.
      5. Character span alignment with chunk offsets if spans are provided.
      6. Page number consistency across evidence, chunk, clause, and item.
      7. Detection of stale evidence (e.g. if referenced entities were unlinked or deleted).
    """
    issues: list[EvidenceValidationIssue] = []
    lineage_intact = True
    text_verified = True
    page_verified = True

    # 1. Verify parent contract
    contract = db.query(Contract).filter(Contract.id == evidence.contract_id).first()
    if not contract:
        issues.append(
            EvidenceValidationIssue(
                issue_type="missing_contract",
                severity="error",
                message=f"Parent contract '{evidence.contract_id}' does not exist in database.",
                field="contract_id",
            )
        )
        lineage_intact = False

    # 2. Verify source item
    source_item = None
    if evidence.source_item_type == "clause":
        source_item = db.query(Clause).filter(Clause.id == evidence.source_item_id).first()
    elif evidence.source_item_type == "obligation":
        source_item = db.query(Obligation).filter(Obligation.id == evidence.source_item_id).first()
    elif evidence.source_item_type == "contract_fact":
        source_item = db.query(ContractFact).filter(ContractFact.id == evidence.source_item_id).first()
    else:
        issues.append(
            EvidenceValidationIssue(
                issue_type="invalid_source_type",
                severity="error",
                message=f"Unsupported source_item_type '{evidence.source_item_type}'.",
                field="source_item_type",
            )
        )
        lineage_intact = False

    if source_item is None:
        issues.append(
            EvidenceValidationIssue(
                issue_type="missing_source_item",
                severity="error",
                message=f"Source item of type '{evidence.source_item_type}' with id '{evidence.source_item_id}' not found.",
                field="source_item_id",
            )
        )
        lineage_intact = False
    else:
        # Check source item contract ownership
        if getattr(source_item, "contract_id", None) != evidence.contract_id:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="contract_mismatch",
                    severity="error",
                    message=f"Source item belongs to contract '{source_item.contract_id}', not '{evidence.contract_id}'.",
                    field="contract_id",
                )
            )
            lineage_intact = False

    # 3. Verify referenced clause if present
    clause = None
    if evidence.source_clause_id:
        clause = db.query(Clause).filter(Clause.id == evidence.source_clause_id).first()
        if not clause:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="missing_clause",
                    severity="error",
                    message=f"Referenced source_clause_id '{evidence.source_clause_id}' does not exist.",
                    field="source_clause_id",
                )
            )
            lineage_intact = False
        elif clause.contract_id != evidence.contract_id:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="contract_mismatch",
                    severity="error",
                    message=f"Referenced clause belongs to contract '{clause.contract_id}', not '{evidence.contract_id}'.",
                    field="source_clause_id",
                )
            )
            lineage_intact = False

    # 4. Verify referenced chunk if present
    chunk = None
    if evidence.source_chunk_id:
        chunk = db.query(DocumentChunk).filter(DocumentChunk.id == evidence.source_chunk_id).first()
        if not chunk:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="missing_chunk",
                    severity="error",
                    message=f"Referenced source_chunk_id '{evidence.source_chunk_id}' does not exist.",
                    field="source_chunk_id",
                )
            )
            lineage_intact = False
        elif chunk.contract_id != evidence.contract_id:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="contract_mismatch",
                    severity="error",
                    message=f"Referenced chunk belongs to contract '{chunk.contract_id}', not '{evidence.contract_id}'.",
                    field="source_chunk_id",
                )
            )
            lineage_intact = False

    # 5. Verify page number consistency
    expected_page = None
    if chunk:
        expected_page = chunk.page_number
    elif clause and clause.page_number:
        expected_page = clause.page_number
    elif source_item and getattr(source_item, "page_number", None):
        expected_page = getattr(source_item, "page_number")

    if expected_page is not None and evidence.page_number is not None:
        if evidence.page_number != expected_page:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="page_mismatch",
                    severity="error",
                    message=f"Evidence page {evidence.page_number} does not match structural source page {expected_page}.",
                    field="page_number",
                )
            )
            page_verified = False

    # 6. Verify verbatim text matching and character spans
    target_corpus = None
    if chunk and chunk.text:
        target_corpus = chunk.text
    elif clause and clause.verbatim_text:
        target_corpus = clause.verbatim_text
    elif source_item:
        if hasattr(source_item, "verbatim_text") and source_item.verbatim_text:
            target_corpus = source_item.verbatim_text
        elif hasattr(source_item, "verbatim_evidence") and source_item.verbatim_evidence:
            target_corpus = source_item.verbatim_evidence

    if target_corpus:
        clean_evidence_text = evidence.source_text.strip().lower()
        clean_corpus_text = target_corpus.strip().lower()
        if clean_evidence_text not in clean_corpus_text:
            issues.append(
                EvidenceValidationIssue(
                    issue_type="text_mismatch",
                    severity="error",
                    message="Verbatim evidence text was not found in referenced chunk or clause content.",
                    field="source_text",
                )
            )
            text_verified = False
        else:
            # Check character span bounds if provided
            if evidence.char_start is not None and evidence.char_end is not None:
                # If offsets fall within target_corpus length, check substring directly
                if evidence.char_end <= len(target_corpus):
                    span_slice = target_corpus[evidence.char_start:evidence.char_end].strip().lower()
                    if clean_evidence_text != span_slice:
                        # Non-fatal warning if offsets differ due to normalization / chunk offset basis
                        issues.append(
                            EvidenceValidationIssue(
                                issue_type="span_mismatch",
                                severity="warning",
                                message=f"Character span [{evidence.char_start}:{evidence.char_end}] does not exactly match slice in source chunk.",
                                field="char_start",
                            )
                        )

    # 7. Overall status evaluation
    has_errors = any(i.severity == "error" for i in issues)
    is_valid = not has_errors

    if is_valid:
        status_str = "valid"
    elif not lineage_intact:
        status_str = "broken_lineage"
    elif not text_verified:
        status_str = "text_mismatch"
    elif not page_verified:
        status_str = "page_mismatch"
    else:
        status_str = "stale"

    return SingleEvidenceValidationResult(
        evidence_id=evidence.id,
        is_valid=is_valid,
        status=status_str,
        issues=issues,
        lineage_intact=lineage_intact,
        text_verified=text_verified,
        page_verified=page_verified,
    )


def validate_contract_evidence(
    db: Session,
    contract_id: uuid.UUID,
    evidence_id: Optional[uuid.UUID] = None,
) -> EvidenceValidationSummary:
    """
    Validates all evidence records for a given contract (or a specific evidence record).
    Returns a comprehensive validation report.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    query = db.query(Evidence).filter(Evidence.contract_id == contract_id)
    if evidence_id:
        query = query.filter(Evidence.id == evidence_id)

    evidence_items = query.order_by(Evidence.page_number.asc().nulls_last(), Evidence.created_at.asc()).all()

    results: list[SingleEvidenceValidationResult] = []
    valid_count = 0
    invalid_count = 0
    stale_count = 0

    for item in evidence_items:
        res = validate_single_evidence(db=db, evidence=item)
        results.append(res)
        if res.is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            if res.status in ("broken_lineage", "stale"):
                stale_count += 1

    return EvidenceValidationSummary(
        contract_id=contract_id,
        total_checked=len(results),
        valid_count=valid_count,
        invalid_count=invalid_count,
        stale_count=stale_count,
        results=results,
    )
