"""
ContractIQ — Cross-Contract Comparison Schemas (Phase 11A–11E)

Defines Pydantic v2 schemas for:
  - 11A: Strongly typed comparison request and response models
  - 11B: Structured field comparisons (ContractFact, Obligation, Contract metadata)
  - 11C: Evidence-backed comparison with full 6-tier lineage
  - 11D: Deterministic comparison differences / risk signals (higher/lower value, notice differences, etc.)
  - 11E: API validation (2-10 contracts, non-empty, deduplicated)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.rag import CitationVerificationStatus


class DifferenceType(str, Enum):
    """Type of deterministic difference identified between contracts."""
    VALUE_DIFFERENCE = "value_difference"
    NUMERIC_COMPARISON = "numeric_comparison"
    TIMEFRAME_DIFFERENCE = "timeframe_difference"
    TERMS_MISMATCH = "terms_mismatch"
    MISSING_TERM = "missing_term"
    IDENTICAL = "identical"


class DifferenceSeverity(str, Enum):
    """Informational flag for deterministic comparison variance."""
    INFO = "info"
    VARIANCE = "variance"
    ATTENTION = "attention"


# ====================================================================
# Evidence & Lineage Schemas for Comparison
# ====================================================================

class ComparisonEvidenceCitation(BaseModel):
    """
    Evidence citation supporting a compared contractual value.
    Preserves 6-tier lineage: comparison → fact/obligation/clause → chunk → page → contract.
    """
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID.")
    source_item_type: str = Field(..., description="Entity type: contract_fact, obligation, clause, or metadata.")
    source_item_id: Optional[uuid.UUID] = Field(default=None, description="Linked entity UUID.")
    chunk_id: Optional[uuid.UUID] = Field(default=None, description="Referenced chunk UUID.")
    page_number: Optional[int] = Field(default=None, ge=1, description="1-indexed source PDF page number.")
    section_header: Optional[str] = Field(default=None, description="Section heading from source chunk.")
    verbatim_quote: Optional[str] = Field(default=None, description="Exact quoted text from contract.")
    verification_status: CitationVerificationStatus = Field(
        default=CitationVerificationStatus.VALID,
        description="Deterministic verification outcome.",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Notes regarding verification or wrong-contract detection.",
    )

    model_config = ConfigDict(from_attributes=True)


class ComparedContractValue(BaseModel):
    """
    Value of a specific field for a single contract, with availability flag and evidence.
    """
    contract_id: uuid.UUID
    contract_title: str
    is_available: bool = Field(
        ...,
        description="True if structured data was found; False if missing/unavailable.",
    )
    value: Optional[str] = Field(
        default=None,
        description="Normalized string value of the field, or None if unavailable.",
    )
    numeric_value: Optional[float] = Field(
        default=None,
        description="Parsed numeric value if applicable (e.g. monetary amount, day count).",
    )
    evidence: Optional[ComparisonEvidenceCitation] = Field(
        default=None,
        description="Evidence citation proving the extracted value.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Field Comparison & Deterministic Differences
# ====================================================================

class DeterministicFieldDifference(BaseModel):
    """
    Deterministic rule-based variance analysis between compared values.
    Calculated strictly in application code without LLM guessing.
    """
    difference_type: DifferenceType
    severity: DifferenceSeverity
    summary: str = Field(
        ...,
        description="Deterministic explanation of the variance (e.g., 'Apex Cloud notice is 30 days shorter than Beta Data').",
    )
    highest_contract_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Contract with highest numeric value if applicable.",
    )
    lowest_contract_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Contract with lowest numeric value if applicable.",
    )
    variance_ratio: Optional[float] = Field(
        default=None,
        description="Ratio or percentage variance between values if numeric.",
    )

    model_config = ConfigDict(from_attributes=True)


class FieldComparisonRow(BaseModel):
    """
    Comparison row for an individual field across all queried contracts.
    """
    field_key: str = Field(..., description="Canonical field identifier (e.g., contract_value, notice_period, liability_cap).")
    field_label: str = Field(..., description="Human-readable label for the compared field.")
    values_by_contract: dict[str, ComparedContractValue] = Field(
        ...,
        description="Map of contract_id string to ComparedContractValue.",
    )
    has_variance: bool = Field(
        default=False,
        description="True if any two available contract values differ.",
    )
    missing_in_contracts: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of contract IDs where this field was not found / unavailable.",
    )
    deterministic_difference: Optional[DeterministicFieldDifference] = Field(
        default=None,
        description="Deterministic analysis of differences across contracts for this field.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Obligation Summary Comparison
# ====================================================================

class ObligationComparisonItem(BaseModel):
    """A compared obligation between contracts."""
    contract_id: uuid.UUID
    contract_title: str
    obligation_id: uuid.UUID
    title: str
    description: Optional[str] = None
    responsible_party: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    deadline_info: Optional[str] = None
    page_number: Optional[int] = None
    evidence: Optional[ComparisonEvidenceCitation] = None

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Request & Response Models
# ====================================================================

class ContractComparisonRequest(BaseModel):
    """
    Request payload for comparing 2 to 10 contracts.
    """
    contract_ids: list[uuid.UUID] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of 2 to 10 contract UUIDs to compare.",
        examples=[
            [
                "8d9c7b46-6355-4640-af75-3f699a19aad0",
                "940e4058-13ee-4097-bc7d-56b871ccfbfe",
            ]
        ],
    )
    field_keys: Optional[list[str]] = Field(
        default=None,
        description="Optional subset of field keys to compare. Defaults to all standard fields if omitted.",
    )
    include_obligations: bool = Field(
        default=True,
        description="Whether to include structured obligation comparison across contracts.",
    )

    @field_validator("contract_ids")
    @classmethod
    def validate_unique_contracts(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate contract IDs are not allowed in comparison request.")
        return v

    model_config = ConfigDict(from_attributes=True)


class ContractMetadataHeader(BaseModel):
    """Metadata summary header for each compared contract."""
    contract_id: uuid.UUID
    title: str
    vendor: Optional[str] = None
    contract_type: Optional[str] = None
    status: str
    page_count: Optional[int] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    contract_value: Optional[float] = None
    currency: Optional[str] = None
    has_auto_renewal: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class ContractComparisonResponse(BaseModel):
    """
    Unified response payload for Cross-Contract Comparison API (Phase 11A–11E).
    """
    total_contracts: int = Field(..., ge=2, le=10, description="Total number of contracts compared.")
    contract_headers: list[ContractMetadataHeader] = Field(
        ...,
        description="High-level metadata for each evaluated contract.",
    )
    fields_compared: list[FieldComparisonRow] = Field(
        ...,
        description="Deterministic matrix of compared contract fields with evidence and differences.",
    )
    obligations: list[ObligationComparisonItem] = Field(
        default_factory=list,
        description="Extracted obligations for all compared contracts with evidence lineage.",
    )
    total_fields: int = 0
    total_variances_found: int = 0
    missing_data_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of missing/unavailable fields per contract ID string.",
    )
    compared_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of comparison execution.",
    )

    model_config = ConfigDict(from_attributes=True)
