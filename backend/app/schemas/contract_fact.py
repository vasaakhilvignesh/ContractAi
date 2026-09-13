"""
ContractIQ — Contract Fact Schemas (Phase 6D)

Defines Pydantic v2 schemas for structured contract-level fact extraction,
API request/response models, and strict validation types.

Lineage:
  Contract → DocumentChunk → Clause → ContractFact
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FactKey(str, Enum):
    """
    Standard contract-level fact categories recognized by ContractIQ.
    """
    EFFECTIVE_DATE = "effective_date"
    EXPIRATION_DATE = "expiration_date"
    CONTRACT_VALUE = "contract_value"
    PAYMENT_TERMS = "payment_terms"
    CURRENCY = "currency"
    PARTIES = "parties"
    GOVERNING_LAW = "governing_law"
    NOTICE_PERIOD = "notice_period"
    RENEWAL_TERM = "renewal_term"
    TERMINATION_NOTICE_PERIOD = "termination_notice_period"
    LIABILITY_CAP = "liability_cap"
    INDEMNIFICATION_CAP = "indemnification_cap"
    DISPUTE_FORUM = "dispute_forum"
    CONFIDENTIALITY_PERIOD = "confidentiality_period"
    OTHER = "other"


# ====================================================================
# LLM Extraction Schemas (Used with Phase 6A StructuredLLMProvider)
# ====================================================================

class ExtractedFactLLM(BaseModel):
    """
    Single contract-level fact extracted by the LLM from a legal clause.
    """
    fact_key: FactKey = Field(
        description=(
            "Standard identifier or category for this fact (e.g., effective_date, "
            "expiration_date, contract_value, payment_terms, currency, parties, "
            "governing_law, notice_period, renewal_term, termination_notice_period, "
            "liability_cap, dispute_forum, confidentiality_period, other)."
        ),
    )
    fact_value: str = Field(
        description=(
            "Normalized, concise textual value of the fact (e.g., '2025-01-01', "
            "'Acme Corp and Wayne Enterprises', 'State of Delaware', '30 days', "
            "'USD 1,200,000', 'Net 30'). Do NOT invent or assume values."
        ),
    )
    fact_value_json: Optional[str] = Field(
        default=None,
        description="Optional JSON-serialized representation for multi-valued or structured facts (e.g. JSON list of party names).",
    )
    verbatim_evidence: str = Field(
        description="Exact verbatim excerpt from the source clause establishing this fact.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score for this fact (0.0 to 1.0).",
    )


class ClauseFactExtractionResult(BaseModel):
    """
    Structured extraction payload returned by the LLM for a single clause.
    """
    facts: list[ExtractedFactLLM] = Field(
        default_factory=list,
        description="List of contractual facts identified within the clause.",
    )
    has_facts: bool = Field(
        default=False,
        description="Boolean indicator whether contract-level facts were identified.",
    )


# ====================================================================
# API & Persistence Schemas
# ====================================================================

class ContractFactBase(BaseModel):
    """Base fields representing an extracted contract fact."""
    fact_key: str = Field(description="Standard fact identifier (e.g. effective_date, governing_law, notice_period).")
    fact_value: Optional[str] = Field(default=None, description="Extracted textual or normalized value of the fact.")
    fact_value_json: Optional[str] = Field(default=None, description="Optional JSON-serialized representation for structured facts.")
    verbatim_evidence: Optional[str] = Field(default=None, description="Exact quoted text supporting this fact.")
    page_number: Optional[int] = Field(default=None, description="1-indexed source PDF page number.")
    confidence: Optional[float] = Field(default=None, description="Extraction confidence score (0.0 to 1.0).")
    source_clause_id: Optional[uuid.UUID] = Field(default=None, description="Source clause UUID.")
    source_chunk_id: Optional[uuid.UUID] = Field(default=None, description="Source document chunk UUID.")


class ContractFactResponse(ContractFactBase):
    """API response model for a persisted ContractFact."""
    id: uuid.UUID
    contract_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractFactExtractionRequest(BaseModel):
    """Request payload for triggering contract fact extraction."""
    force_reextract: bool = Field(
        default=False,
        description="If True, clears previously extracted facts and runs fresh extraction.",
    )


class ContractFactExtractionResponse(BaseModel):
    """Response payload returned after extracting facts from a contract."""
    contract_id: uuid.UUID
    total_clauses_analyzed: int
    total_facts_extracted: int
    facts_by_key: dict[str, int]
    facts: list[ContractFactResponse]


class ContractFactListResponse(BaseModel):
    """Response payload for listing extracted facts for a contract."""
    contract_id: uuid.UUID
    total_facts: int
    facts: list[ContractFactResponse]
