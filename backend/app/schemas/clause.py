"""
ContractIQ — Clause Schemas (Phase 6B)

Defines Pydantic v2 schemas for structured clause extraction, API request/response models,
and strict validation types.

Lineage:
  Contract → DocumentChunk → Clause
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClauseType(str, Enum):
    """
    Standard legal clause categories recognized by ContractIQ.
    """
    TERMINATION = "termination"
    LIABILITY = "liability"
    INDEMNIFICATION = "indemnification"
    AUTO_RENEWAL = "auto_renewal"
    CONFIDENTIALITY = "confidentiality"
    PAYMENT = "payment"
    GOVERNING_LAW = "governing_law"
    DISPUTE_RESOLUTION = "dispute_resolution"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    WARRANTY = "warranty"
    DATA_PRIVACY = "data_privacy"
    OTHER = "other"


# ====================================================================
# LLM Extraction Schemas (Used with Phase 6A StructuredLLMProvider)
# ====================================================================

class ExtractedClauseLLM(BaseModel):
    """
    Single legal clause extracted by the LLM from a document chunk.
    """
    clause_type: ClauseType = Field(
        description="Legal category of the clause (e.g. termination, liability, auto_renewal)."
    )
    clause_label: Optional[str] = Field(
        default=None,
        description="Section heading, clause number, or label (e.g., 'Section 8.2 — Termination for Cause').",
    )
    verbatim_text: str = Field(
        description="Exact verbatim excerpt from the chunk representing the operative clause text.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this clause classification (0.0 to 1.0).",
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Brief rationale explaining why this excerpt constitutes the specified clause type.",
    )


class ChunkClauseExtractionResult(BaseModel):
    """
    Structured extraction payload returned by the LLM for a single chunk.
    """
    clauses: list[ExtractedClauseLLM] = Field(
        default_factory=list,
        description="List of operative contractual clauses identified within the chunk.",
    )
    has_clauses: bool = Field(
        default=False,
        description="Boolean indicator whether operative legal clauses were identified.",
    )


# ====================================================================
# API & Persistence Schemas
# ====================================================================

class ClauseBase(BaseModel):
    """Base fields representing an extracted clause."""
    clause_type: str = Field(description="Legal clause classification.")
    clause_label: Optional[str] = Field(default=None, description="Section heading or clause label.")
    verbatim_text: str = Field(description="Exact verbatim text of the clause.")
    page_number: Optional[int] = Field(default=None, description="1-indexed source PDF page number.")
    source_chunk_id: Optional[uuid.UUID] = Field(default=None, description="Source document chunk UUID.")
    extraction_confidence: Optional[float] = Field(default=None, description="Extraction confidence score.")


class ClauseResponse(ClauseBase):
    """API response model for a persisted Clause."""
    id: uuid.UUID
    contract_id: uuid.UUID
    is_reviewed: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractClauseExtractionRequest(BaseModel):
    """Request payload for triggering clause extraction."""
    force_reextract: bool = Field(
        default=False,
        description="If True, clears previously extracted clauses and runs fresh extraction.",
    )


class ContractClauseExtractionResponse(BaseModel):
    """Response payload returned after extracting clauses from a contract."""
    contract_id: uuid.UUID
    total_chunks_processed: int
    total_clauses_extracted: int
    clauses_by_type: dict[str, int]
    clauses: list[ClauseResponse]


class ContractClauseListResponse(BaseModel):
    """Response payload for listing extracted clauses for a contract."""
    contract_id: uuid.UUID
    total_clauses: int
    clauses: list[ClauseResponse]
