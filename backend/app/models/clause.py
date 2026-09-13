"""
ContractIQ — Clause Model

Represents a structured clause extracted from a contract document.
Clauses are the primary evidence units: every obligation and risk signal
must trace back to a specific clause.

Evidence lineage:
  Contract → DocumentChunk → Clause → Obligation / RiskSignal

Design notes:
  - clause_type classifies the legal function of the clause
    (e.g., Termination, Liability, Indemnification, Auto-Renewal).
  - verbatim_text stores the exact quoted text from the contract,
    preserving authenticity of citations.
  - page_number is denormalized here (also on DocumentChunk) to allow
    direct citation without always joining through document_chunks.
  - extracted_facts stores structured JSON data from Phase 4 LLM extraction
    (e.g., {"notice_period_days": 15, "auto_renewal": true}).
    Using Text for now; can be migrated to JSONB in a future migration.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Clause(Base):
    __tablename__ = "clauses"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this clause",
    )

    # ----------------------------------------------------------------
    # Evidence Lineage FKs
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent contract this clause belongs to",
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source document chunk from which this clause was extracted",
    )

    # ----------------------------------------------------------------
    # Clause Classification
    # ----------------------------------------------------------------
    clause_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=(
            "Legal clause type: "
            "termination | liability | indemnification | auto_renewal | "
            "payment | confidentiality | governing_law | dispute_resolution | other"
        ),
    )
    clause_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Human-readable clause label (e.g., 'Section 7.2 — Early Termination')",
    )

    # ----------------------------------------------------------------
    # Evidence Text (Critical for citation authenticity)
    # ----------------------------------------------------------------
    verbatim_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Exact verbatim text of the clause as it appears in the contract",
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Page number in the source PDF where this clause appears (1-indexed)",
    )

    # ----------------------------------------------------------------
    # Structured Extraction (Phase 4+)
    # ----------------------------------------------------------------
    extracted_facts: Mapped[str | None] = mapped_column(
        Text,  # Will be migrated to JSONB in a future migration if needed
        nullable=True,
        comment=(
            "JSON object of structured facts extracted from this clause by the LLM. "
            "Example: {\"notice_period_days\": 15, \"auto_renewal\": true}. "
            "Populated in Phase 4."
        ),
    )
    extraction_confidence: Mapped[float | None] = mapped_column(
        # Using String here to avoid needing Numeric import; can use Float
        nullable=True,
        comment="LLM extraction confidence score (0.0 to 1.0). Populated in Phase 4.",
    )

    # ----------------------------------------------------------------
    # Review State
    # ----------------------------------------------------------------
    is_reviewed: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Whether a human reviewer has verified this clause extraction",
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
        back_populates="clauses",
    )
    source_chunk: Mapped["DocumentChunk | None"] = relationship(  # noqa: F821
        "DocumentChunk",
        back_populates="clauses",
    )
    obligations: Mapped[list["Obligation"]] = relationship(  # noqa: F821
        "Obligation",
        back_populates="source_clause",
    )
    risk_signals: Mapped[list["RiskSignal"]] = relationship(  # noqa: F821
        "RiskSignal",
        back_populates="source_clause",
    )
    evidence: Mapped[list["Evidence"]] = relationship(  # noqa: F821
        "Evidence",
        back_populates="source_clause",
    )

    def __repr__(self) -> str:
        return (
            f"<Clause id={self.id} type={self.clause_type!r} "
            f"page={self.page_number} contract_id={self.contract_id}>"
        )
