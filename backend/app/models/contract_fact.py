"""
ContractIQ — Contract Fact Model (Phase 6D)

Represents an individual structured contract-level fact extracted from contract clauses/chunks.
Preserves strict evidence lineage:
  Contract → DocumentChunk → Clause → ContractFact
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContractFact(Base):
    __tablename__ = "contract_facts"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this extracted contract fact",
    )

    # ----------------------------------------------------------------
    # Evidence Lineage FKs
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent contract this fact belongs to",
    )
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source clause from which this fact was extracted",
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source document chunk for direct evidence reference",
    )

    # ----------------------------------------------------------------
    # Fact Content
    # ----------------------------------------------------------------
    fact_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Standard fact identifier (e.g., effective_date, governing_law, liability_cap)",
    )
    fact_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted textual or normalized value of the fact",
    )
    fact_value_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional JSON-serialized representation for multi-valued or complex facts",
    )
    verbatim_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Exact quoted text from the contract/clause supporting this fact",
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Page number in the source PDF where the fact evidence appears (1-indexed)",
    )
    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="LLM extraction confidence score (0.0 to 1.0)",
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
        back_populates="facts",
    )
    source_clause: Mapped["Clause | None"] = relationship(  # noqa: F821
        "Clause",
    )
    source_chunk: Mapped["DocumentChunk | None"] = relationship(  # noqa: F821
        "DocumentChunk",
    )

    def __repr__(self) -> str:
        return (
            f"<ContractFact id={self.id} key={self.fact_key!r} "
            f"value={self.fact_value!r} contract_id={self.contract_id}>"
        )
