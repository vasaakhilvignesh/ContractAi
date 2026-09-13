"""
ContractIQ — Evidence Schemas (Phase 7A)

Defines Pydantic v2 schemas for the persistent Evidence model, supporting
source lineage, character span offsets, and immutability invariants.

Lineage Hierarchy:
  evidence → source item → clause → chunk → page → contract
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceSourceItemType(str, Enum):
    """
    Standard domain entity types that can be linked to evidence records.
    """
    CLAUSE = "clause"
    OBLIGATION = "obligation"
    CONTRACT_FACT = "contract_fact"


# ====================================================================
# API & Persistence Schemas
# ====================================================================

class EvidenceBase(BaseModel):
    """
    Base schema for an evidence record capturing verbatim contract text,
    provenance, and structural lineage.
    """
    contract_id: uuid.UUID = Field(
        description="Parent contract UUID.",
    )
    source_item_type: EvidenceSourceItemType | str = Field(
        description="Type of source item supported: clause, obligation, or contract_fact.",
    )
    source_item_id: uuid.UUID = Field(
        description="UUID of the linked source entity (clause, obligation, or fact).",
    )
    source_item_reference: Optional[str] = Field(
        default=None,
        description="Canonical identifier for the source item (e.g. 'clause:<uuid>', 'obligation:<uuid>').",
    )
    source_clause_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Direct clause reference in the lineage chain (clause -> chunk -> page -> contract).",
    )
    source_chunk_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Direct document chunk reference for the evidence text.",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-indexed source PDF page number.",
    )
    source_text: str = Field(
        description="Verbatim contract text serving as evidence.",
    )
    char_start: Optional[int] = Field(
        default=None,
        ge=0,
        description="Character start offset of the span within normalized page or chunk text.",
    )
    char_end: Optional[int] = Field(
        default=None,
        ge=0,
        description="Character end offset of the span within normalized page or chunk text.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases_and_reference(cls, values):
        if isinstance(values, dict):
            # Allow 'text' alias for source_text
            if "text" in values and "source_text" not in values:
                values["source_text"] = values["text"]

            # Allow 'span' tuple alias for (char_start, char_end)
            if "span" in values and values["span"]:
                span = values["span"]
                if len(span) == 2:
                    values["char_start"], values["char_end"] = span

            # Auto-populate source_item_reference if missing
            stype = values.get("source_item_type")
            sid = values.get("source_item_id")
            if not values.get("source_item_reference") and stype and sid:
                type_str = stype.value if hasattr(stype, "value") else str(stype)
                values["source_item_reference"] = f"{type_str}:{sid}"

        return values

    @property
    def span(self) -> tuple[Optional[int], Optional[int]]:
        """Returns character span tuple (char_start, char_end)."""
        return (self.char_start, self.char_end)


class EvidenceCreate(EvidenceBase):
    """Payload for creating a persistent Evidence record."""
    pass


class EvidenceResponse(EvidenceBase):
    """Response payload representing a persisted Evidence record."""
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceLineage(BaseModel):
    """
    Structured representation of the full evidence lineage trace:
    evidence → source item → clause → chunk → page → contract
    """
    evidence_id: uuid.UUID
    source_item_type: str
    source_item_id: uuid.UUID
    source_item_reference: Optional[str] = None
    clause_id: Optional[uuid.UUID] = None
    chunk_id: Optional[uuid.UUID] = None
    page_number: Optional[int] = None
    contract_id: uuid.UUID
    source_text: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceListResponse(BaseModel):
    """Response payload for listing evidence records for a contract or item."""
    contract_id: uuid.UUID
    total_evidence: int
    evidence: list[EvidenceResponse]


class EvidenceLineageListResponse(BaseModel):
    """Response payload for listing evidence with complete lineage traces."""
    contract_id: uuid.UUID
    total_evidence: int
    evidence: list[EvidenceLineage]


# ====================================================================
# Phase 7C Validation Schemas
# ====================================================================

class EvidenceValidationIssue(BaseModel):
    """Specific validation issue discovered for an evidence record."""
    issue_type: str = Field(
        description="Category of issue: missing_contract, missing_source_item, contract_mismatch, "
                    "missing_chunk, missing_clause, page_mismatch, text_mismatch, span_mismatch, stale_evidence."
    )
    severity: str = Field(
        description="Severity level: error | warning"
    )
    message: str = Field(
        description="Human-readable description of the validation issue."
    )
    field: Optional[str] = Field(
        default=None,
        description="Affected field or relationship."
    )


class SingleEvidenceValidationResult(BaseModel):
    """Validation result for an individual evidence record."""
    evidence_id: uuid.UUID
    is_valid: bool
    status: str = Field(
        description="Overall status: 'valid', 'stale', 'broken_lineage', 'text_mismatch'"
    )
    issues: list[EvidenceValidationIssue] = Field(
        default_factory=list,
        description="List of detected validation issues, if any."
    )
    lineage_intact: bool = Field(
        description="True if contract, source item, clause, and chunk references are referentially intact."
    )
    text_verified: bool = Field(
        description="True if source_text matches or cleanly substrings within its referenced chunk."
    )
    page_verified: bool = Field(
        description="True if page_number matches the parent chunk or clause page number."
    )


class EvidenceValidationSummary(BaseModel):
    """Comprehensive validation summary for all evidence in a contract."""
    contract_id: uuid.UUID
    total_checked: int
    valid_count: int
    invalid_count: int
    stale_count: int
    results: list[SingleEvidenceValidationResult]
