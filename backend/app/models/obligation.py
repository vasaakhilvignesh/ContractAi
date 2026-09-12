"""
ContractIQ — Obligation Model

Represents a contractual obligation extracted from a contract.
An obligation is a binding commitment by a named responsible party
with a defined due date or recurrence frequency.

Evidence lineage:
  Contract → DocumentChunk → Clause → Obligation

Every obligation must trace back to:
  - The contract it belongs to
  - The clause it was extracted from
  - The document chunk that contains the clause
  - The page number for precise citation

Design notes:
  - responsible_party: The entity required to fulfill the obligation
    (e.g., "Vendor", "Customer", "Both Parties").
  - due_date: The specific deadline, if defined.
  - frequency: Recurring obligation cadence (e.g., "Monthly", "Annually").
  - status: Tracks human tracking state (pending → in_progress → completed / overdue).
  - priority: Manually-assigned or rule-derived priority (high / medium / low).
"""

import uuid
from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Obligation(Base):
    __tablename__ = "obligations"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this obligation",
    )

    # ----------------------------------------------------------------
    # Evidence Lineage FKs
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent contract this obligation belongs to",
    )
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source clause from which this obligation was extracted",
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source document chunk for direct evidence reference",
    )

    # ----------------------------------------------------------------
    # Obligation Content
    # ----------------------------------------------------------------
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Short title or description of the obligation",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full obligation description extracted from the contract",
    )
    verbatim_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Exact quoted text from the contract supporting this obligation",
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Page number in the source PDF where the obligation appears (1-indexed)",
    )

    # ----------------------------------------------------------------
    # Obligation Attributes
    # ----------------------------------------------------------------
    responsible_party: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Entity responsible for fulfilling this obligation (e.g., 'Vendor', 'Customer')",
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Specific due date for the obligation, if defined",
    )
    frequency: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Recurrence frequency for ongoing obligations (e.g., 'Monthly', 'Annually', 'On-demand')",
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is a recurring obligation",
    )

    # ----------------------------------------------------------------
    # Tracking State
    # ----------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Tracking status: pending | in_progress | completed | overdue | waived",
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
        comment="Priority level: high | medium | low",
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
        back_populates="obligations",
    )
    source_clause: Mapped["Clause | None"] = relationship(  # noqa: F821
        "Clause",
        back_populates="obligations",
    )
    source_chunk: Mapped["DocumentChunk | None"] = relationship(  # noqa: F821
        "DocumentChunk",
        back_populates="obligations",
    )

    def __repr__(self) -> str:
        return (
            f"<Obligation id={self.id} title={self.title!r} "
            f"status={self.status!r} contract_id={self.contract_id}>"
        )
