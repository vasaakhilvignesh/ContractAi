"""
ContractIQ — Contract Model

Represents a contract document in the system.
Stores metadata about the document and its current processing state.

Evidence lineage root:
  Contract → DocumentChunks → Clauses → Obligations / RiskSignals

Design notes:
- file_path / file_storage_key stores where the original PDF is stored
  (local path in development; object storage key in production).
- processing_status tracks ingestion pipeline state (Phase 2+).
- The vendor/counterparty fields mirror the existing frontend mock data
  and represent the primary contracting parties.
"""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Contract(Base):
    __tablename__ = "contracts"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for the contract",
    )

    # ----------------------------------------------------------------
    # Ownership
    # ----------------------------------------------------------------
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who uploaded this contract",
    )

    # ----------------------------------------------------------------
    # Contract Metadata
    # ----------------------------------------------------------------
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Contract title or document name",
    )
    vendor: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Counterparty / vendor name",
    )
    contract_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Contract type: MSA | NDA | SaaS | PSA | Lease | Employment | Other",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
        comment="Contract lifecycle status: active | expired | pending_review | terminated",
    )

    # ----------------------------------------------------------------
    # Dates
    # ----------------------------------------------------------------
    effective_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date the contract became effective",
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Date the contract expires or auto-renews",
    )

    # ----------------------------------------------------------------
    # Financial
    # ----------------------------------------------------------------
    contract_value: Mapped[float | None] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=True,
        comment="Total contract value in USD (or base currency)",
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
        comment="Currency code for contract_value (ISO 4217)",
    )

    # ----------------------------------------------------------------
    # Document Storage
    # ----------------------------------------------------------------
    file_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Original uploaded filename",
    )
    file_storage_key: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Storage path or object-key for the original PDF file",
    )
    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total page count of the contract document",
    )

    # ----------------------------------------------------------------
    # Processing Pipeline State (Phase 2+)
    # ----------------------------------------------------------------
    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment=(
            "Ingestion pipeline state: "
            "pending | extracting | chunking | embedding | indexing | ready | failed"
        ),
    )
    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Non-sensitive error description if processing failed",
    )

    # ----------------------------------------------------------------
    # Risk Summary (denormalized cache — updated by Phase 4 rules engine)
    # ----------------------------------------------------------------
    risk_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Aggregate risk level: critical | high | medium | low | none",
    )
    has_auto_renewal: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Extracted: whether the contract has an auto-renewal clause",
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
    uploaded_by_user: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        back_populates="contracts",
    )
    document_chunks: Mapped[list["DocumentChunk"]] = relationship(  # noqa: F821
        "DocumentChunk",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.page_number, DocumentChunk.chunk_index",
    )
    clauses: Mapped[list["Clause"]] = relationship(  # noqa: F821
        "Clause",
        back_populates="contract",
        cascade="all, delete-orphan",
    )
    obligations: Mapped[list["Obligation"]] = relationship(  # noqa: F821
        "Obligation",
        back_populates="contract",
        cascade="all, delete-orphan",
    )
    risk_signals: Mapped[list["RiskSignal"]] = relationship(  # noqa: F821
        "RiskSignal",
        back_populates="contract",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        "AuditEvent",
        back_populates="contract",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Contract id={self.id} title={self.title!r} "
            f"vendor={self.vendor!r} status={self.status!r}>"
        )
