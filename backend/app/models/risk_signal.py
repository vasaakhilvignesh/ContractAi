"""
ContractIQ — RiskSignal Model

Represents a deterministic risk flag identified in a contract.

Architecture: ContractIQ uses a two-stage risk analysis approach:
  1. LLM Extraction (Phase 4): Extracts structured facts from clauses
     (e.g., notice_period_days: 15, auto_renewal: true).
  2. Deterministic Rules Engine (Phase 4): Application code evaluates
     structured facts against business rules to produce risk signals.
     The LLM DOES NOT determine risk severity nondeterministically.

Evidence lineage:
  Contract → DocumentChunk → Clause → RiskSignal

Each risk signal must cite:
  - The specific rule that triggered it
  - The extracted fact that triggered the rule
  - The verbatim evidence from the contract
  - The page number for citation
  - The source clause and chunk

Design notes:
  - rule_id: A stable identifier for the business rule (e.g., "RULE_NOTICE_PERIOD_SHORT").
  - triggered_fact: The specific extracted value (e.g., "notice_period_days: 15").
  - recommended_action: Plain-English action item for the procurement team.
  - is_acknowledged: Allows teams to mark a risk as reviewed without dismissing it.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this risk signal",
    )

    # ----------------------------------------------------------------
    # Evidence Lineage FKs
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent contract this risk signal belongs to",
    )
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source clause that triggered this risk signal",
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source document chunk for direct evidence reference",
    )

    # ----------------------------------------------------------------
    # Risk Classification
    # ----------------------------------------------------------------
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Risk severity: critical | high | medium | low",
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment=(
            "Risk category: "
            "termination | liability | renewal | indemnification | payment | "
            "confidentiality | compliance | other"
        ),
    )

    # ----------------------------------------------------------------
    # Rule Traceability (Deterministic Rules Engine)
    # ----------------------------------------------------------------
    rule_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=(
            "Stable identifier for the business rule that fired. "
            "Example: RULE_NOTICE_PERIOD_SHORT, RULE_AUTO_RENEWAL_IMMINENT, "
            "RULE_UNCAPPED_LIABILITY"
        ),
    )
    rule_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Human-readable description of the triggered rule",
    )
    triggered_fact: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment=(
            "The specific extracted fact that triggered this rule. "
            "Example: 'notice_period_days: 15'"
        ),
    )

    # ----------------------------------------------------------------
    # Evidence
    # ----------------------------------------------------------------
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Short risk signal title displayed in the UI",
    )
    verbatim_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Exact quoted text from the contract that supports this risk signal",
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Page number in the source PDF where the risk evidence appears (1-indexed)",
    )

    # ----------------------------------------------------------------
    # Recommended Action
    # ----------------------------------------------------------------
    recommended_action: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Plain-English recommended action for the procurement / legal team",
    )

    # ----------------------------------------------------------------
    # Review State
    # ----------------------------------------------------------------
    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this risk has been acknowledged by a reviewer",
    )
    is_false_positive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this signal has been marked as a false positive by a reviewer",
    )

    # ----------------------------------------------------------------
    # Timestamps
    # ----------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Record last-updated timestamp",
    )

    # ----------------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------------
    contract: Mapped["Contract"] = relationship(  # noqa: F821
        "Contract",
        back_populates="risk_signals",
    )
    source_clause: Mapped["Clause | None"] = relationship(  # noqa: F821
        "Clause",
        back_populates="risk_signals",
    )
    source_chunk: Mapped["DocumentChunk | None"] = relationship(  # noqa: F821
        "DocumentChunk",
        back_populates="risk_signals",
    )

    def __repr__(self) -> str:
        return (
            f"<RiskSignal id={self.id} severity={self.severity!r} "
            f"rule_id={self.rule_id!r} contract_id={self.contract_id}>"
        )
