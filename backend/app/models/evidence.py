"""
ContractIQ — Evidence Model (Phase 7A)

Represents persistent, source-oriented, and immutable contractual evidence.
Every evidence record links an extracted domain entity (clause, obligation, contract fact)
to its underlying textual and structural origin in the contract document.

Evidence Lineage Hierarchy:
  evidence → source item → clause → chunk → page → contract

Design Principles:
  - Source-oriented: Stores exact verbatim source text and character span offsets.
  - Lineage preservation: Retains direct references to source items, clauses, chunks,
    pages, and parent contracts.
  - Immutability: Once created, evidence records represent historical facts and must NEVER
    be modified (no updated_at column, before_update listener blocks mutation).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_evidence_page_number_positive",
        ),
        CheckConstraint(
            "char_start IS NULL OR char_start >= 0",
            name="ck_evidence_char_start_non_negative",
        ),
        CheckConstraint(
            "char_end IS NULL OR (char_start IS NOT NULL AND char_end >= char_start)",
            name="ck_evidence_char_end_gte_start",
        ),
        CheckConstraint(
            "source_item_type IN ('clause', 'obligation', 'contract_fact')",
            name="ck_evidence_source_item_type_valid",
        ),
        Index(
            "ix_evidence_source_item",
            "source_item_type",
            "source_item_id",
        ),
        Index(
            "ix_evidence_contract_page",
            "contract_id",
            "page_number",
        ),
    )

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this evidence record",
    )

    # ----------------------------------------------------------------
    # Parent Contract FK (Mandatory Lineage Root)
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent contract this evidence belongs to",
    )

    # ----------------------------------------------------------------
    # Source Item Reference (clause | obligation | contract_fact)
    # ----------------------------------------------------------------
    source_item_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of source item supported by this evidence: clause | obligation | contract_fact",
    )
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID of the specific source item (clause, obligation, or contract fact)",
    )
    source_item_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Canonical reference identifier for the source item (e.g., 'clause:<uuid>', 'obligation:<uuid>')",
    )

    # ----------------------------------------------------------------
    # Structural Lineage (Clause, Chunk, Page)
    # ----------------------------------------------------------------
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Direct FK to clause in the lineage chain (evidence -> source item -> clause)",
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Direct FK to document chunk containing the source text",
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="1-indexed source PDF page number where this evidence text appears",
    )

    # ----------------------------------------------------------------
    # Verbatim Evidence Text & Span
    # ----------------------------------------------------------------
    source_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Verbatim text quote from the contract document serving as evidence",
    )
    char_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character start offset of the evidence span within normalized text",
    )
    char_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character end offset of the evidence span within normalized text",
    )

    # ----------------------------------------------------------------
    # Timestamp (Immutable after insert — no updated_at)
    # ----------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Evidence creation timestamp — immutable after insert",
    )

    # ----------------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------------
    contract: Mapped["Contract"] = relationship(  # noqa: F821
        "Contract",
        back_populates="evidence",
    )
    source_clause: Mapped["Clause | None"] = relationship(  # noqa: F821
        "Clause",
        foreign_keys=[source_clause_id],
        back_populates="evidence",
    )
    source_chunk: Mapped["DocumentChunk | None"] = relationship(  # noqa: F821
        "DocumentChunk",
        foreign_keys=[source_chunk_id],
    )

    def __init__(self, **kwargs):
        # Auto-populate canonical reference if omitted
        if "source_item_reference" not in kwargs or kwargs["source_item_reference"] is None:
            stype = kwargs.get("source_item_type")
            sid = kwargs.get("source_item_id")
            if stype and sid:
                kwargs["source_item_reference"] = f"{stype}:{sid}"

        # Allow 'text' alias for source_text
        if "text" in kwargs and "source_text" not in kwargs:
            kwargs["source_text"] = kwargs.pop("text")

        # Allow 'span' tuple alias for (char_start, char_end)
        if "span" in kwargs:
            span = kwargs.pop("span")
            if span:
                kwargs["char_start"], kwargs["char_end"] = span

        super().__init__(**kwargs)

    # ----------------------------------------------------------------
    # Property Helpers
    # ----------------------------------------------------------------
    @property
    def text(self) -> str:
        """Alias for source_text."""
        return self.source_text

    @text.setter
    def text(self, value: str) -> None:
        self.source_text = value

    @property
    def span(self) -> tuple[int | None, int | None]:
        """Returns character span tuple (char_start, char_end)."""
        return (self.char_start, self.char_end)

    @property
    def clause(self) -> "Clause | None":  # noqa: F821
        """Convenience alias for source_clause."""
        return self.source_clause

    @property
    def chunk(self) -> "DocumentChunk | None":  # noqa: F821
        """Convenience alias for source_chunk."""
        return self.source_chunk

    def get_lineage(self) -> dict:
        """
        Returns full evidence lineage dictionary:
        evidence → source item → clause → chunk → page → contract
        """
        return {
            "evidence_id": self.id,
            "source_item_type": self.source_item_type,
            "source_item_id": self.source_item_id,
            "source_item_reference": self.source_item_reference or f"{self.source_item_type}:{self.source_item_id}",
            "clause_id": self.source_clause_id,
            "chunk_id": self.source_chunk_id,
            "page_number": self.page_number,
            "contract_id": self.contract_id,
            "source_text": self.source_text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"<Evidence id={self.id} item_type={self.source_item_type!r} "
            f"item_id={self.source_item_id} page={self.page_number} "
            f"contract_id={self.contract_id}>"
        )


@event.listens_for(Evidence, "before_update")
def _prevent_evidence_update(mapper, connection, target):
    """
    Enforces evidence immutability at the SQLAlchemy session level.
    Evidence records are factual observations and cannot be updated once created.
    """
    raise ValueError("Evidence records are source-oriented and immutable; updates are prohibited.")
