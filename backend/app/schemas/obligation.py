"""
ContractIQ — Obligation Schemas (Phase 6C)

Defines Pydantic v2 schemas for structured obligation extraction, API request/response models,
and strict validation types.

Lineage:
  Contract → DocumentChunk → Clause → Obligation
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ObligationType(str, Enum):
    """
    Standard contractual obligation categories recognized by ContractIQ.
    """
    PAYMENT = "payment"
    DELIVERY = "delivery"
    REPORTING = "reporting"
    NOTICE = "notice"
    CONFIDENTIALITY = "confidentiality"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    INSURANCE = "insurance"
    RENEWAL = "renewal"
    TERMINATION = "termination"
    OTHER = "other"


# ====================================================================
# LLM Extraction Schemas (Used with Phase 6A StructuredLLMProvider)
# ====================================================================

class ExtractedObligationLLM(BaseModel):
    """
    Single contractual obligation extracted by the LLM from a legal clause.
    """
    title: str = Field(
        description="Concise summary title of the obligation (e.g., 'Pay Invoices Within 30 Days').",
    )
    description: str = Field(
        description="Detailed description of what action, duty, or constraint must be performed.",
    )
    responsible_party: str = Field(
        description="Entity or party required to perform this obligation (e.g., 'Vendor', 'Customer', 'Both Parties').",
    )
    obligation_type: ObligationType = Field(
        description="Category of the obligation (e.g. payment, delivery, reporting, notice, confidentiality).",
    )
    due_date_description: Optional[str] = Field(
        default=None,
        description="Due date, deadline, or timing trigger if defined (e.g., 'Within 30 days of invoice receipt', 'Annually on Jan 1').",
    )
    frequency: Optional[str] = Field(
        default=None,
        description="Recurrence frequency if ongoing (e.g., 'Monthly', 'Quarterly', 'Annually', 'On-demand', 'One-time').",
    )
    is_recurring: bool = Field(
        default=False,
        description="Whether this obligation recurs periodically over time.",
    )
    verbatim_evidence: str = Field(
        description="Exact verbatim excerpt from the source clause establishing this obligation.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score for this obligation (0.0 to 1.0).",
    )


class ClauseObligationExtractionResult(BaseModel):
    """
    Structured extraction payload returned by the LLM for a single clause.
    """
    obligations: list[ExtractedObligationLLM] = Field(
        default_factory=list,
        description="List of operative contractual obligations identified within the clause.",
    )
    has_obligations: bool = Field(
        default=False,
        description="Boolean indicator whether operative obligations were identified.",
    )


# ====================================================================
# API & Persistence Schemas
# ====================================================================

class ObligationBase(BaseModel):
    """Base fields representing a contractual obligation."""
    title: str = Field(description="Short title or summary of the obligation.")
    description: Optional[str] = Field(default=None, description="Detailed description of the obligation.")
    responsible_party: Optional[str] = Field(default=None, description="Responsible entity or party.")
    obligation_type: Optional[str] = Field(default=None, description="Category/type of obligation.")
    due_date: Optional[date] = Field(default=None, description="Specific calendar due date if defined.")
    deadline_info: Optional[str] = Field(default=None, description="Textual due date / deadline description.")
    frequency: Optional[str] = Field(default=None, description="Recurrence frequency.")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring obligation.")
    verbatim_evidence: Optional[str] = Field(default=None, description="Exact quoted text supporting this obligation.")
    page_number: Optional[int] = Field(default=None, description="1-indexed source PDF page number.")
    source_clause_id: Optional[uuid.UUID] = Field(default=None, description="Source clause UUID.")
    source_chunk_id: Optional[uuid.UUID] = Field(default=None, description="Source document chunk UUID.")
    status: str = Field(default="pending", description="Tracking status: pending | in_progress | completed | overdue | waived.")
    priority: str = Field(default="medium", description="Priority level: high | medium | low.")
    extraction_confidence: Optional[float] = Field(default=None, description="Extraction confidence score.")


class ObligationResponse(ObligationBase):
    """API response model for a persisted Obligation."""
    id: uuid.UUID
    contract_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractObligationExtractionRequest(BaseModel):
    """Request payload for triggering obligation extraction."""
    force_reextract: bool = Field(
        default=False,
        description="If True, clears previously extracted obligations and runs fresh extraction.",
    )


class ContractObligationExtractionResponse(BaseModel):
    """Response payload returned after extracting obligations from a contract."""
    contract_id: uuid.UUID
    total_clauses_analyzed: int
    total_obligations_extracted: int
    obligations_by_party: dict[str, int]
    obligations_by_type: dict[str, int]
    obligations: list[ObligationResponse]


class ContractObligationListResponse(BaseModel):
    """Response payload for listing extracted obligations for a contract."""
    contract_id: uuid.UUID
    total_obligations: int
    obligations: list[ObligationResponse]
