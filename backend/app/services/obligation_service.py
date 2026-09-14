"""
ContractIQ — Obligation Service Layer (Phase 12A–12E)

Implements core domain operations for:
  - 12A: Obligation query & retrieval foundation.
  - 12B: Contract-scoped retrieval with multi-facet filtering (responsible party, obligation type,
         tracking status, priority, recurrence, due dates, deadline triggers).
  - 12C: 6-tier evidence lineage resolution and deterministic validation:
         obligation → clause → chunk → page → contract.
         Detects and flags WRONG_CONTRACT, CHUNK_NOT_FOUND, PAGE_MISMATCH, and TEXT_MISMATCH.
  - 12D: Deterministic obligation analysis (summary metrics, party breakdowns, recurrence counts,
         overdue/upcoming counts, cadence classification, confidence tiers) computed 100% in code.
  - 12E: Scoping enforcement and error contract handling.
"""

from collections import Counter
from datetime import date, timedelta
import logging
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.clause import Clause
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.schemas.obligation import ObligationResponse
from app.schemas.obligation_api import (
    ObligationAnalysisSummary,
    ObligationDerivedAnalysis,
    ObligationDetailResponse,
    ObligationEvidenceCitation,
    ObligationQueryRequest,
    ObligationQueryResponse,
)
from app.schemas.rag import CitationVerificationStatus

logger = logging.getLogger(__name__)


# ====================================================================
# Domain Exceptions
# ====================================================================

class ObligationServiceError(Exception):
    """Base exception for obligation service failures."""
    pass


class ContractNotFoundError(ObligationServiceError):
    """Raised when the requested contract does not exist."""
    pass


class ObligationNotFoundError(ObligationServiceError):
    """Raised when a specific obligation ID does not exist."""
    pass


class ObligationScopingError(ObligationServiceError):
    """Raised when an obligation does not belong to the queried contract."""
    pass


# ====================================================================
# Deterministic Analysis Helpers (12D)
# ====================================================================

def compute_derived_analysis(
    obligation: Obligation,
    ref_date: date,
) -> ObligationDerivedAnalysis:
    """
    Computes deterministic derived status for a single obligation.
    Computed purely via code algorithms without LLM guessing.
    """
    has_explicit_due_date = obligation.due_date is not None
    is_overdue = False
    days_until_due: Optional[int] = None

    if obligation.due_date:
        delta = (obligation.due_date - ref_date).days
        days_until_due = delta
        # If status is not already completed/waived, and due_date is in past
        if delta < 0 and obligation.status not in ("completed", "waived"):
            is_overdue = True

    has_deadline_trigger = bool(obligation.deadline_info and obligation.deadline_info.strip())

    # Cadence standardizer
    cadence: Optional[str] = None
    if obligation.frequency:
        freq_clean = obligation.frequency.strip().lower()
        if "month" in freq_clean:
            cadence = "Monthly"
        elif "quarter" in freq_clean:
            cadence = "Quarterly"
        elif "annual" in freq_clean or "year" in freq_clean:
            cadence = "Annually"
        elif "week" in freq_clean:
            cadence = "Weekly"
        elif "daily" in freq_clean or "day" in freq_clean:
            cadence = "Daily"
        elif "demand" in freq_clean:
            cadence = "On-demand"
        else:
            cadence = obligation.frequency.strip().title()

    # Confidence tier
    conf = obligation.extraction_confidence
    if conf is None:
        conf_tier = "unrated"
    elif conf >= 0.85:
        conf_tier = "high"
    elif conf >= 0.60:
        conf_tier = "medium"
    else:
        conf_tier = "low"

    return ObligationDerivedAnalysis(
        has_explicit_due_date=has_explicit_due_date,
        is_overdue=is_overdue,
        days_until_due=days_until_due,
        has_deadline_trigger=has_deadline_trigger,
        is_recurring=obligation.is_recurring,
        cadence=cadence,
        confidence_tier=conf_tier,
    )


# ====================================================================
# Evidence Lineage Resolution & Verification (12C)
# ====================================================================

def resolve_obligation_lineage(
    db: Session,
    contract_id: uuid.UUID,
    obligation: Obligation,
) -> ObligationEvidenceCitation:
    """
    Assembles and deterministically verifies the 6-tier evidence lineage for an obligation:
    obligation → clause → chunk → page → contract.
    """
    resolved_clause_id = obligation.source_clause_id
    resolved_chunk_id = obligation.source_chunk_id
    resolved_page_number = obligation.page_number
    resolved_section_header: Optional[str] = None
    verbatim_quote = obligation.verbatim_evidence

    status = CitationVerificationStatus.VALID
    notes_list: list[str] = []

    # 1. Resolve source clause
    clause: Optional[Clause] = None
    if resolved_clause_id:
        clause = db.query(Clause).filter(Clause.id == resolved_clause_id).first()
        if clause:
            # Check contract ownership of clause
            if clause.contract_id != contract_id:
                status = CitationVerificationStatus.WRONG_CONTRACT
                notes_list.append(f"Source clause belongs to foreign contract {clause.contract_id}.")
            if not resolved_chunk_id:
                resolved_chunk_id = clause.source_chunk_id
            if resolved_page_number is None:
                resolved_page_number = clause.page_number

    # 2. Resolve source chunk
    chunk: Optional[DocumentChunk] = None
    if resolved_chunk_id:
        chunk = db.query(DocumentChunk).filter(DocumentChunk.id == resolved_chunk_id).first()
        if not chunk:
            if status == CitationVerificationStatus.VALID:
                status = CitationVerificationStatus.CHUNK_NOT_FOUND
            notes_list.append(f"Referenced chunk {resolved_chunk_id} does not exist.")
        else:
            # Check contract ownership of chunk
            if chunk.contract_id != contract_id:
                status = CitationVerificationStatus.WRONG_CONTRACT
                notes_list.append(f"Referenced chunk belongs to foreign contract {chunk.contract_id}.")
            resolved_section_header = chunk.section_header
            if resolved_page_number is None:
                resolved_page_number = chunk.page_number

    # 3. Check page consistency
    if chunk and resolved_page_number is not None:
        if chunk.page_number is not None and chunk.page_number != resolved_page_number:
            if status == CitationVerificationStatus.VALID:
                status = CitationVerificationStatus.PAGE_MISMATCH
            notes_list.append(f"Obligation page {resolved_page_number} differs from chunk page {chunk.page_number}.")

    # 4. Check verbatim quote matching against chunk or clause text
    corpus_text: Optional[str] = None
    if chunk and chunk.text:
        corpus_text = chunk.text
    elif clause and clause.verbatim_text:
        corpus_text = clause.verbatim_text

    if verbatim_quote and corpus_text:
        clean_quote = verbatim_quote.strip().lower()
        clean_corpus = corpus_text.strip().lower()
        if clean_quote not in clean_corpus:
            if status == CitationVerificationStatus.VALID:
                status = CitationVerificationStatus.TEXT_MISMATCH
            notes_list.append("Verbatim quote does not match source chunk/clause text.")

    if not verbatim_quote and not corpus_text and status == CitationVerificationStatus.VALID:
        notes_list.append("No verbatim text available to cross-verify.")

    verification_notes = "; ".join(notes_list) if notes_list else "Lineage verified intact."

    return ObligationEvidenceCitation(
        contract_id=contract_id,
        obligation_id=obligation.id,
        clause_id=resolved_clause_id,
        chunk_id=resolved_chunk_id,
        page_number=resolved_page_number,
        section_header=resolved_section_header,
        verbatim_quote=verbatim_quote,
        verification_status=status,
        verification_notes=verification_notes,
    )


# ====================================================================
# Obligation Query & Filtering Engine (12A, 12B, 12D, 12E)
# ====================================================================

def query_contract_obligations(
    db: Session,
    contract_id: uuid.UUID,
    filters: Optional[ObligationQueryRequest] = None,
) -> ObligationQueryResponse:
    """
    Retrieves, filters, validates lineage, and computes deterministic analysis for a contract's obligations.
    Strictly scoped to the provided contract_id.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    if filters is None:
        filters = ObligationQueryRequest()

    ref_date = filters.reference_date or date.today()

    query = db.query(Obligation).filter(Obligation.contract_id == contract_id)

    # Filter by responsible_party
    if filters.responsible_party and filters.responsible_party.strip():
        query = query.filter(
            Obligation.responsible_party.ilike(f"%{filters.responsible_party.strip()}%")
        )

    # Filter by obligation_type
    if filters.obligation_type and filters.obligation_type.strip():
        query = query.filter(
            Obligation.obligation_type == filters.obligation_type.strip().lower()
        )

    # Filter by status
    if filters.status and filters.status.strip():
        query = query.filter(
            Obligation.status == filters.status.strip().lower()
        )

    # Filter by priority
    if filters.priority and filters.priority.strip():
        query = query.filter(
            Obligation.priority == filters.priority.strip().lower()
        )

    # Filter by is_recurring
    if filters.is_recurring is not None:
        query = query.filter(Obligation.is_recurring == filters.is_recurring)

    # Filter by has_due_date
    if filters.has_due_date is True:
        query = query.filter(Obligation.due_date.isnot(None))
    elif filters.has_due_date is False:
        query = query.filter(Obligation.due_date.is_(None))

    # Filter by due_date range
    if filters.due_date_from is not None:
        query = query.filter(Obligation.due_date >= filters.due_date_from)
    if filters.due_date_to is not None:
        query = query.filter(Obligation.due_date <= filters.due_date_to)

    obligations = query.order_by(
        Obligation.page_number.asc().nullslast(),
        Obligation.due_date.asc().nullslast(),
        Obligation.created_at.asc(),
    ).all()

    # Build detailed responses with lineage and derived metrics
    detail_items: list[ObligationDetailResponse] = []
    party_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    lineage_status_counts: Counter[str] = Counter()

    recurring_count = 0
    non_recurring_count = 0
    with_due_date_count = 0
    with_deadline_info_count = 0
    overdue_count = 0
    upcoming_count = 0
    upcoming_cutoff = ref_date + timedelta(days=30)

    for ob in obligations:
        party_key = ob.responsible_party or "Unspecified"
        party_counts[party_key] += 1

        type_key = ob.obligation_type or "unspecified"
        type_counts[type_key] += 1

        status_counts[ob.status] += 1
        priority_counts[ob.priority] += 1

        if ob.is_recurring:
            recurring_count += 1
        else:
            non_recurring_count += 1

        if ob.due_date:
            with_due_date_count += 1
            if ob.due_date < ref_date and ob.status not in ("completed", "waived"):
                overdue_count += 1
            elif ref_date <= ob.due_date <= upcoming_cutoff and ob.status not in ("completed", "waived"):
                upcoming_count += 1

        if ob.deadline_info and ob.deadline_info.strip():
            with_deadline_info_count += 1

        # Resolve lineage if requested
        citation: Optional[ObligationEvidenceCitation] = None
        if filters.include_lineage:
            citation = resolve_obligation_lineage(db, contract_id, ob)
            lineage_status_counts[citation.verification_status.value] += 1

        derived = compute_derived_analysis(ob, ref_date)

        detail_response = ObligationDetailResponse(
            id=ob.id,
            contract_id=ob.contract_id,
            title=ob.title,
            description=ob.description,
            responsible_party=ob.responsible_party,
            obligation_type=ob.obligation_type,
            due_date=ob.due_date,
            deadline_info=ob.deadline_info,
            frequency=ob.frequency,
            is_recurring=ob.is_recurring,
            verbatim_evidence=ob.verbatim_evidence,
            page_number=ob.page_number,
            source_clause_id=ob.source_clause_id,
            source_chunk_id=ob.source_chunk_id,
            status=ob.status,
            priority=ob.priority,
            extraction_confidence=ob.extraction_confidence,
            created_at=ob.created_at,
            updated_at=ob.updated_at,
            evidence_citation=citation,
            derived_analysis=derived,
        )
        detail_items.append(detail_response)

    summary = ObligationAnalysisSummary(
        total_obligations=len(detail_items),
        by_responsible_party=dict(party_counts),
        by_obligation_type=dict(type_counts),
        by_status=dict(status_counts),
        by_priority=dict(priority_counts),
        recurring_count=recurring_count,
        non_recurring_count=non_recurring_count,
        with_due_date_count=with_due_date_count,
        with_deadline_info_count=with_deadline_info_count,
        overdue_count=overdue_count,
        upcoming_count=upcoming_count,
        lineage_integrity_summary=dict(lineage_status_counts),
    )

    return ObligationQueryResponse(
        contract_id=contract_id,
        contract_title=contract.title,
        total_obligations=len(detail_items),
        items=detail_items,
        analysis=summary,
    )


def get_single_obligation_detail(
    db: Session,
    contract_id: uuid.UUID,
    obligation_id: uuid.UUID,
    include_lineage: bool = True,
    reference_date: Optional[date] = None,
) -> ObligationDetailResponse:
    """
    Retrieves a single obligation by ID, enforcing strict contract scoping.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    ob = db.query(Obligation).filter(Obligation.id == obligation_id).first()
    if not ob:
        raise ObligationNotFoundError(f"Obligation with id '{obligation_id}' not found.")

    # Strict scoping check
    if ob.contract_id != contract_id:
        raise ObligationScopingError(
            f"Obligation with id '{obligation_id}' belongs to contract '{ob.contract_id}', not '{contract_id}'."
        )

    ref_date = reference_date or date.today()
    citation: Optional[ObligationEvidenceCitation] = None
    if include_lineage:
        citation = resolve_obligation_lineage(db, contract_id, ob)

    derived = compute_derived_analysis(ob, ref_date)

    return ObligationDetailResponse(
        id=ob.id,
        contract_id=ob.contract_id,
        title=ob.title,
        description=ob.description,
        responsible_party=ob.responsible_party,
        obligation_type=ob.obligation_type,
        due_date=ob.due_date,
        deadline_info=ob.deadline_info,
        frequency=ob.frequency,
        is_recurring=ob.is_recurring,
        verbatim_evidence=ob.verbatim_evidence,
        page_number=ob.page_number,
        source_clause_id=ob.source_clause_id,
        source_chunk_id=ob.source_chunk_id,
        status=ob.status,
        priority=ob.priority,
        extraction_confidence=ob.extraction_confidence,
        created_at=ob.created_at,
        updated_at=ob.updated_at,
        evidence_citation=citation,
        derived_analysis=derived,
    )
