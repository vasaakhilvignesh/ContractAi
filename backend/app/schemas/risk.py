"""
ContractIQ — Risk Signals & Evaluation Schemas (Phase 8A & Phase 8D)

Defines Pydantic v2 models for deterministic risk rule evaluation, risk signals,
lineage tracing, and analysis responses.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RiskSeverity(str, Enum):
    """Deterministic severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskCategory(str, Enum):
    """Standard risk categories."""
    RENEWAL = "renewal"
    TERMINATION = "termination"
    LIABILITY = "liability"
    INDEMNIFICATION = "indemnification"
    PAYMENT = "payment"
    COMPLIANCE = "compliance"
    CONFIDENTIALITY = "confidentiality"
    CRITICAL_TERMS = "critical_terms"
    OTHER = "other"


# ====================================================================
# Risk Signal API Schemas
# ====================================================================

class RiskSignalBase(BaseModel):
    """Base schema for a detected contract risk signal."""
    contract_id: uuid.UUID = Field(
        description="Parent contract UUID.",
    )
    rule_id: str = Field(
        description="Unique identifier of the deterministic rule that triggered this signal.",
    )
    rule_description: str = Field(
        description="Human-readable description of the triggered rule.",
    )
    severity: RiskSeverity | str = Field(
        description="Severity level: critical | high | medium | low.",
    )
    category: Optional[RiskCategory | str] = Field(
        default=None,
        description="Risk functional category.",
    )
    title: str = Field(
        description="Short summary title of the risk signal.",
    )
    triggered_fact: Optional[str] = Field(
        default=None,
        description="Specific fact value or condition that triggered this rule.",
    )
    verbatim_evidence: Optional[str] = Field(
        default=None,
        description="Verbatim contract text quote supporting this risk.",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-indexed source PDF page number.",
    )
    recommended_action: Optional[str] = Field(
        default=None,
        description="Actionable guidance for legal/procurement reviewer.",
    )
    source_clause_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Direct FK to source clause in lineage chain.",
    )
    source_chunk_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Direct FK to source document chunk in lineage chain.",
    )
    is_acknowledged: bool = Field(
        default=False,
        description="Whether risk has been acknowledged by a human reviewer.",
    )
    is_false_positive: bool = Field(
        default=False,
        description="Whether risk was marked false positive by reviewer.",
    )


class RiskSignalResponse(RiskSignalBase):
    """Response model for a persisted risk signal with complete lineage."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskEvaluationRequest(BaseModel):
    """Request payload for running deterministic risk rule evaluation."""
    force_reevaluate: bool = Field(
        default=False,
        description="If True, clears previous risk signals and re-evaluates all rules from scratch.",
    )


class RiskEvaluationResponse(BaseModel):
    """Response payload returned when risk rules are evaluated on a contract."""
    contract_id: uuid.UUID
    total_rules_evaluated: int
    total_risks_detected: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    signals: list[RiskSignalResponse]


class RiskSignalListResponse(BaseModel):
    """Response payload for listing risk signals for a contract."""
    contract_id: uuid.UUID
    total_risks: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    signals: list[RiskSignalResponse]
