"""
ContractIQ — Obligation API & Analysis Schemas (Phase 12A–12E)

Defines strongly typed Pydantic v2 request/response schemas for:
  - 12A: Obligation query & retrieval foundation.
  - 12B: Multi-facet filtering (responsible party, obligation type, status, priority, recurrence, due date bounds).
  - 12C: Evidence-backed lineage citations (6-tier lineage: obligation → clause → chunk → page → contract)
         and deterministic lineage status validation (valid, broken, wrong_contract, text_mismatch, page_mismatch).
  - 12D: Deterministic obligation analysis (summary metrics, party breakdowns, recurrence counts, overdue/upcoming counts,
         due date distribution, confidence metrics).
  - 12E: Scoped REST response structures and error contracts.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.obligation import ObligationResponse, ObligationType
from app.schemas.rag import CitationVerificationStatus


# ====================================================================
# Lineage & Evidence Schemas
# ====================================================================

class ObligationEvidenceCitation(BaseModel):
    """
    Evidence citation representing the 6-tier provenance of a contractual obligation:
    obligation → clause → chunk → page → contract.
    """
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID.")
    obligation_id: uuid.UUID = Field(..., description="Target obligation UUID.")
    clause_id: Optional[uuid.UUID] = Field(default=None, description="Source clause UUID if resolved.")
    chunk_id: Optional[uuid.UUID] = Field(default=None, description="Source document chunk UUID if resolved.")
    page_number: Optional[int] = Field(default=None, ge=1, description="1-indexed source PDF page number.")
    section_header: Optional[str] = Field(default=None, description="Section heading from source chunk or clause.")
    verbatim_quote: Optional[str] = Field(default=None, description="Exact verbatim excerpt from contract supporting this obligation.")
    verification_status: CitationVerificationStatus = Field(
        default=CitationVerificationStatus.VALID,
        description="Deterministic lineage verification outcome (valid, text_mismatch, page_mismatch, chunk_not_found, wrong_contract).",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of verification outcome or any detected lineage discrepancies.",
    )


# ====================================================================
# Enhanced Obligation Detail Response (With Lineage & Analysis)
# ====================================================================

class ObligationDerivedAnalysis(BaseModel):
    """
    Deterministic derived attributes for an obligation computed strictly from structured data.
    Clearly separates extracted data from code-derived flags (no LLM guessing).
    """
    has_explicit_due_date: bool = Field(..., description="Whether a calendar due date is explicitly defined.")
    is_overdue: bool = Field(..., description="Whether due_date has passed relative to reference date (if due_date present).")
    days_until_due: Optional[int] = Field(default=None, description="Days remaining until due date, or negative if past due.")
    has_deadline_trigger: bool = Field(..., description="Whether textual deadline trigger info is present.")
    is_recurring: bool = Field(..., description="Whether this is a recurring ongoing obligation.")
    cadence: Optional[str] = Field(default=None, description="Standardized cadence representation from frequency.")
    confidence_tier: str = Field(..., description="Confidence classification: high (>=0.85), medium (>=0.60), low (<0.60), or unrated.")


class ObligationDetailResponse(ObligationResponse):
    """
    Comprehensive obligation response with complete evidence lineage and deterministic derived analysis.
    """
    evidence_citation: Optional[ObligationEvidenceCitation] = Field(
        default=None,
        description="Full 6-tier evidence lineage citation with deterministic verification.",
    )
    derived_analysis: Optional[ObligationDerivedAnalysis] = Field(
        default=None,
        description="Deterministic derived analysis calculated 100% in application code.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Obligation Aggregate Analysis & Summary (12D)
# ====================================================================

class ObligationAnalysisSummary(BaseModel):
    """
    Deterministic summary metrics and aggregations for contract obligations.
    Computed purely via code algorithms over structured database fields.
    """
    total_obligations: int = Field(..., ge=0, description="Total number of obligations matching query.")
    by_responsible_party: dict[str, int] = Field(
        default_factory=dict,
        description="Obligation counts grouped by responsible party.",
    )
    by_obligation_type: dict[str, int] = Field(
        default_factory=dict,
        description="Obligation counts grouped by obligation category.",
    )
    by_status: dict[str, int] = Field(
        default_factory=dict,
        description="Obligation counts grouped by tracking status (pending, in_progress, completed, overdue, waived).",
    )
    by_priority: dict[str, int] = Field(
        default_factory=dict,
        description="Obligation counts grouped by priority (high, medium, low).",
    )
    recurring_count: int = Field(..., ge=0, description="Count of recurring obligations.")
    non_recurring_count: int = Field(..., ge=0, description="Count of one-off / fixed obligations.")
    with_due_date_count: int = Field(..., ge=0, description="Count of obligations with calendar due dates.")
    with_deadline_info_count: int = Field(..., ge=0, description="Count of obligations with textual deadline conditions.")
    overdue_count: int = Field(..., ge=0, description="Count of obligations that are past due relative to evaluation date.")
    upcoming_count: int = Field(..., ge=0, description="Count of obligations due within the next 30 days.")
    lineage_integrity_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of evidence lineage verification statuses across returned obligations.",
    )


# ====================================================================
# Request & Response Envelopes
# ====================================================================

class ObligationQueryRequest(BaseModel):
    """
    Payload for advanced contract obligation queries and multi-facet filtering.
    """
    responsible_party: Optional[str] = Field(
        default=None,
        description="Case-insensitive substring match for responsible party (e.g., 'Vendor', 'Customer').",
    )
    obligation_type: Optional[str] = Field(
        default=None,
        description="Category/type of obligation (e.g., payment, reporting, notice, delivery).",
    )
    status: Optional[str] = Field(
        default=None,
        description="Tracking status: pending | in_progress | completed | overdue | waived.",
    )
    priority: Optional[str] = Field(
        default=None,
        description="Priority level: high | medium | low.",
    )
    is_recurring: Optional[bool] = Field(
        default=None,
        description="Filter by recurring (True) or non-recurring (False) obligations.",
    )
    has_due_date: Optional[bool] = Field(
        default=None,
        description="If True, only obligations with explicit due dates; if False, only without.",
    )
    due_date_from: Optional[date] = Field(
        default=None,
        description="Inclusive start date for due_date filtering.",
    )
    due_date_to: Optional[date] = Field(
        default=None,
        description="Inclusive end date for due_date filtering.",
    )
    include_lineage: bool = Field(
        default=True,
        description="Whether to resolve and verify full 6-tier evidence lineage for each obligation.",
    )
    reference_date: Optional[date] = Field(
        default=None,
        description="Reference calendar date for overdue/upcoming calculations (defaults to today).",
    )


class ObligationQueryResponse(BaseModel):
    """
    Structured response envelope returned by the Obligation API.
    """
    contract_id: uuid.UUID = Field(..., description="Target contract UUID.")
    contract_title: Optional[str] = Field(default=None, description="Title of the target contract.")
    total_obligations: int = Field(..., ge=0, description="Total matching obligations.")
    items: list[ObligationDetailResponse] = Field(
        default_factory=list,
        description="List of obligation details with evidence lineage and derived analysis.",
    )
    analysis: ObligationAnalysisSummary = Field(
        ...,
        description="Deterministic analysis aggregations and summary metrics.",
    )
