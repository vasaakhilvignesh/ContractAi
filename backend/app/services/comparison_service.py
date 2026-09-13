"""
ContractIQ — Cross-Contract Comparison Service (Phase 11A–11E)

Implements:
  - 11A: Strongly typed comparison service layer.
  - 11B: Structured cross-contract comparison across 2-10 contracts using extracted
         ContractFact, Obligation, and Contract metadata. Never invents missing data.
  - 11C: Evidence-backed comparison preserving 6-tier lineage:
         comparison → fact/obligation/clause → chunk → page → contract.
         Detects and flags wrong-contract evidence.
  - 11D: Deterministic comparison/variance analysis (numeric comparison, notice differences,
         missing terms) calculated 100% in application code without LLM guessing.
  - 11E: Contract scoping validation, handling empty/missing data and edge cases.
"""

import logging
import re
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.contract_fact import ContractFact
from app.models.document_chunk import DocumentChunk
from app.models.obligation import Obligation
from app.schemas.comparison import (
    ComparedContractValue,
    ComparisonEvidenceCitation,
    ContractComparisonRequest,
    ContractComparisonResponse,
    ContractMetadataHeader,
    DeterministicFieldDifference,
    DifferenceSeverity,
    DifferenceType,
    FieldComparisonRow,
    ObligationComparisonItem,
)
from app.schemas.rag import CitationVerificationStatus

logger = logging.getLogger(__name__)

# Standard canonical comparison fields
STANDARD_COMPARISON_FIELDS = [
    ("effective_date", "Effective Date"),
    ("expiration_date", "Expiration Date"),
    ("contract_value", "Contract Value"),
    ("payment_terms", "Payment Terms"),
    ("notice_period", "Notice Period"),
    ("termination_notice_period", "Termination Notice Period"),
    ("renewal_term", "Renewal Term"),
    ("liability_cap", "Limitation of Liability"),
    ("indemnification_cap", "Indemnification"),
    ("governing_law", "Governing Law"),
    ("dispute_forum", "Dispute Forum"),
]


# ====================================================================
# Exceptions
# ====================================================================

class ComparisonServiceError(Exception):
    """Base exception for contract comparison errors."""
    pass


class ComparisonScopingError(ComparisonServiceError):
    """Raised when contracts requested for comparison do not exist or are invalid."""
    pass


# ====================================================================
# Parsing & Numeric Extraction Helpers
# ====================================================================

def parse_numeric_quantity(text: Optional[str]) -> Optional[float]:
    """
    Extracts leading or first meaningful numeric quantity from a value string
    (e.g., '$1,200,000' -> 1200000.0, '30 days' -> 30.0, '60 days' -> 60.0).
    """
    if not text:
        return None
    # Remove currency symbols and commas
    cleaned = text.replace(",", "").replace("$", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def calculate_deterministic_field_difference(
    field_key: str,
    field_label: str,
    values_by_contract: dict[str, ComparedContractValue],
) -> Optional[DeterministicFieldDifference]:
    """
    Evaluates deterministic variances between contract values for a specific field.
    Operates strictly without LLM calls.
    """
    available_items = [
        (cid, cv) for cid, cv in values_by_contract.items() if cv.is_available and cv.value is not None
    ]

    # If 0 or 1 contract has this field, analyze missingness
    if len(available_items) == 0:
        return DeterministicFieldDifference(
            difference_type=DifferenceType.MISSING_TERM,
            severity=DifferenceSeverity.ATTENTION,
            summary=f"No contracts have '{field_label}' specified.",
        )

    if len(available_items) < len(values_by_contract):
        missing_titles = [
            cv.contract_title for cv in values_by_contract.values() if not cv.is_available
        ]
        return DeterministicFieldDifference(
            difference_type=DifferenceType.MISSING_TERM,
            severity=DifferenceSeverity.VARIANCE,
            summary=f"'{field_label}' is missing in: {', '.join(missing_titles)}.",
        )

    # All contracts have the field available. Check if all values are identical.
    raw_values = [cv.value.strip().lower() for _, cv in available_items]
    if len(set(raw_values)) == 1:
        return DeterministicFieldDifference(
            difference_type=DifferenceType.IDENTICAL,
            severity=DifferenceSeverity.INFO,
            summary=f"All contracts have identical '{field_label}': '{available_items[0][1].value}'.",
        )

    # Check numeric comparison (e.g. contract_value, notice_period)
    numeric_items = [
        (cid, cv.numeric_value, cv.contract_title)
        for cid, cv in available_items
        if cv.numeric_value is not None
    ]

    if len(numeric_items) == len(available_items):
        # All have numeric values
        sorted_numeric = sorted(numeric_items, key=lambda x: x[1])
        lowest = sorted_numeric[0]
        highest = sorted_numeric[-1]

        if highest[1] != lowest[1]:
            diff = highest[1] - lowest[1]
            unit = "days" if "notice" in field_key.lower() else "units"
            summary_str = (
                f"Variance of {diff:.1f} {unit}: highest in '{highest[2]}' ({highest[1]:.1f}), "
                f"lowest in '{lowest[2]}' ({lowest[1]:.1f})."
            )
            ratio = round(highest[1] / lowest[1], 2) if lowest[1] > 0 else None
            diff_type = (
                DifferenceType.TIMEFRAME_DIFFERENCE
                if "notice" in field_key.lower() or "term" in field_key.lower()
                else DifferenceType.NUMERIC_COMPARISON
            )
            return DeterministicFieldDifference(
                difference_type=diff_type,
                severity=DifferenceSeverity.VARIANCE,
                summary=summary_str,
                highest_contract_id=uuid.UUID(highest[0]),
                lowest_contract_id=uuid.UUID(lowest[0]),
                variance_ratio=ratio,
            )

    # Non-numeric textual mismatch
    summary_parts = [f"'{cv.contract_title}': {cv.value}" for _, cv in available_items]
    return DeterministicFieldDifference(
        difference_type=DifferenceType.TERMS_MISMATCH,
        severity=DifferenceSeverity.VARIANCE,
        summary=f"Variance detected: {'; '.join(summary_parts)}.",
    )


# ====================================================================
# Main Comparison Service Implementation
# ====================================================================

def compare_contracts_structured(
    db: Session,
    request: ContractComparisonRequest,
) -> ContractComparisonResponse:
    """
    Executes deterministic, evidence-backed cross-contract comparison across 2-10 contracts.
    """
    # 1. Scoping & contract existence verification
    contracts = db.query(Contract).filter(Contract.id.in_(request.contract_ids)).all()
    found_ids = {c.id for c in contracts}
    missing_ids = [cid for cid in request.contract_ids if cid not in found_ids]
    if missing_ids:
        raise ComparisonScopingError(
            f"The following contracts do not exist or are inaccessible: {[str(cid) for cid in missing_ids]}"
        )

    # Maintain deterministic request ordering
    ordered_contracts = [next(c for c in contracts if c.id == cid) for cid in request.contract_ids]
    contract_by_id = {c.id: c for c in ordered_contracts}

    # 2. Build metadata headers
    headers: list[ContractMetadataHeader] = []
    for c in ordered_contracts:
        headers.append(
            ContractMetadataHeader(
                contract_id=c.id,
                title=c.title,
                vendor=c.vendor,
                contract_type=c.contract_type,
                status=c.status,
                page_count=c.page_count,
                effective_date=str(c.effective_date) if c.effective_date else None,
                expiry_date=str(c.expiry_date) if c.expiry_date else None,
                contract_value=float(c.contract_value) if c.contract_value is not None else None,
                currency=c.currency,
                has_auto_renewal=c.has_auto_renewal,
            )
        )

    # 3. Load extracted ContractFacts for all target contracts
    facts = (
        db.query(ContractFact)
        .filter(ContractFact.contract_id.in_(request.contract_ids))
        .all()
    )

    # Group facts by (contract_id, fact_key) -> latest fact
    facts_by_contract_and_key: dict[tuple[uuid.UUID, str], ContractFact] = {}
    for f in facts:
        facts_by_contract_and_key[(f.contract_id, f.fact_key.lower())] = f

    # Determine field list to compare
    if request.field_keys:
        fields_to_compare = [
            (fk.lower(), fk.replace("_", " ").title())
            for fk in request.field_keys
        ]
    else:
        fields_to_compare = STANDARD_COMPARISON_FIELDS

    # 4. Construct Field Comparison Rows
    field_rows: list[FieldComparisonRow] = []
    missing_counts: dict[str, int] = {str(c.id): 0 for c in ordered_contracts}
    total_variances = 0

    for field_key, field_label in fields_to_compare:
        values_by_contract: dict[str, ComparedContractValue] = {}
        missing_contracts: list[uuid.UUID] = []

        for c in ordered_contracts:
            cid_str = str(c.id)
            fact = facts_by_contract_and_key.get((c.id, field_key))

            # Fallback to contract top-level metadata if fact is not explicitly in contract_facts
            val_str: Optional[str] = None
            evidence_citation: Optional[ComparisonEvidenceCitation] = None

            if fact and fact.fact_value:
                val_str = fact.fact_value.strip()

                # Build evidence citation with 6-tier lineage
                evidence_citation = ComparisonEvidenceCitation(
                    contract_id=c.id,
                    source_item_type="contract_fact",
                    source_item_id=fact.id,
                    chunk_id=fact.source_chunk_id,
                    page_number=fact.page_number,
                    verbatim_quote=fact.verbatim_evidence,
                    verification_status=CitationVerificationStatus.VALID,
                    verification_notes="Matched to structured ContractFact record.",
                )

                # Defensive lineage check: ensure chunk actually belongs to this contract
                if fact.source_chunk_id:
                    chunk_rec = db.query(DocumentChunk).filter(DocumentChunk.id == fact.source_chunk_id).first()
                    if chunk_rec and chunk_rec.contract_id != c.id:
                        evidence_citation.verification_status = CitationVerificationStatus.WRONG_CONTRACT
                        evidence_citation.verification_notes = (
                            f"Wrong contract: fact references chunk {fact.source_chunk_id} "
                            f"belonging to contract {chunk_rec.contract_id}."
                        )
            else:
                # Check contract metadata fallback
                if field_key == "effective_date" and c.effective_date:
                    val_str = str(c.effective_date)
                    evidence_citation = ComparisonEvidenceCitation(
                        contract_id=c.id,
                        source_item_type="contract_metadata",
                        verification_status=CitationVerificationStatus.VALID,
                        verification_notes="Populated from contract record metadata.",
                    )
                elif field_key == "expiration_date" and c.expiry_date:
                    val_str = str(c.expiry_date)
                    evidence_citation = ComparisonEvidenceCitation(
                        contract_id=c.id,
                        source_item_type="contract_metadata",
                        verification_status=CitationVerificationStatus.VALID,
                        verification_notes="Populated from contract record metadata.",
                    )
                elif field_key == "contract_value" and c.contract_value is not None:
                    curr = f" {c.currency}" if c.currency else ""
                    val_str = f"{c.contract_value}{curr}"
                    evidence_citation = ComparisonEvidenceCitation(
                        contract_id=c.id,
                        source_item_type="contract_metadata",
                        verification_status=CitationVerificationStatus.VALID,
                        verification_notes="Populated from contract record metadata.",
                    )

            if val_str is not None:
                numeric_val = parse_numeric_quantity(val_str)
                values_by_contract[cid_str] = ComparedContractValue(
                    contract_id=c.id,
                    contract_title=c.title,
                    is_available=True,
                    value=val_str,
                    numeric_value=numeric_val,
                    evidence=evidence_citation,
                )
            else:
                missing_contracts.append(c.id)
                missing_counts[cid_str] += 1
                values_by_contract[cid_str] = ComparedContractValue(
                    contract_id=c.id,
                    contract_title=c.title,
                    is_available=False,
                    value=None,
                    numeric_value=None,
                    evidence=None,
                )

        # Evaluate deterministic differences
        diff = calculate_deterministic_field_difference(
            field_key=field_key,
            field_label=field_label,
            values_by_contract=values_by_contract,
        )

        has_var = diff is not None and diff.difference_type != DifferenceType.IDENTICAL
        if has_var:
            total_variances += 1

        field_rows.append(
            FieldComparisonRow(
                field_key=field_key,
                field_label=field_label,
                values_by_contract=values_by_contract,
                has_variance=has_var,
                missing_in_contracts=missing_contracts,
                deterministic_difference=diff,
            )
        )

    # 5. Obligations comparison (if requested)
    obligation_items: list[ObligationComparisonItem] = []
    if request.include_obligations:
        obs = (
            db.query(Obligation)
            .filter(Obligation.contract_id.in_(request.contract_ids))
            .order_by(Obligation.contract_id, Obligation.created_at.asc())
            .all()
        )
        for ob in obs:
            c_title = contract_by_id[ob.contract_id].title

            # Build obligation evidence citation
            ob_evidence = ComparisonEvidenceCitation(
                contract_id=ob.contract_id,
                source_item_type="obligation",
                source_item_id=ob.id,
                chunk_id=ob.source_chunk_id,
                page_number=ob.page_number,
                verbatim_quote=ob.description,
                verification_status=CitationVerificationStatus.VALID,
                verification_notes="Structured obligation extracted from contract.",
            )

            # Scoping check: verify chunk contract ownership
            if ob.source_chunk_id:
                chunk_rec = db.query(DocumentChunk).filter(DocumentChunk.id == ob.source_chunk_id).first()
                if chunk_rec and chunk_rec.contract_id != ob.contract_id:
                    ob_evidence.verification_status = CitationVerificationStatus.WRONG_CONTRACT
                    ob_evidence.verification_notes = (
                        f"Wrong contract: obligation references chunk {ob.source_chunk_id} "
                        f"belonging to contract {chunk_rec.contract_id}."
                    )

            obligation_items.append(
                ObligationComparisonItem(
                    contract_id=ob.contract_id,
                    contract_title=c_title,
                    obligation_id=ob.id,
                    title=ob.title,
                    description=ob.description,
                    responsible_party=ob.responsible_party,
                    priority=ob.priority,
                    due_date=str(ob.due_date) if ob.due_date else None,
                    deadline_info=ob.deadline_info,
                    page_number=ob.page_number,
                    evidence=ob_evidence,
                )
            )

    return ContractComparisonResponse(
        total_contracts=len(ordered_contracts),
        contract_headers=headers,
        fields_compared=field_rows,
        obligations=obligation_items,
        total_fields=len(field_rows),
        total_variances_found=total_variances,
        missing_data_summary=missing_counts,
    )
