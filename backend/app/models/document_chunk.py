"""
ContractIQ — DocumentChunk Model

Represents a text segment (chunk) extracted from a contract PDF.
This is the fundamental unit for vector search and evidence retrieval.

Evidence lineage:
  Contract → DocumentChunk → Clause / RiskSignal / Obligation

pgvector integration:
  The `embedding` column stores the dense vector representation of the
  chunk text. Dimension is finalized at 768 dimensions for Google Gemini
  gemini-embedding-2 (DEC-024).
  Alembic migration enforces Vector(768) and creates an HNSW index
  with vector_cosine_ops for approximate nearest-neighbor search.

Key design decisions:
  - page_number: Critical for citation. Every chunk records its source page.
  - chunk_index: Ordering within a page / document for context reconstruction.
  - char_start / char_end: Character offsets within the extracted page text,
    enabling precise text highlighting in the frontend.
  - section_header: Nearest detected section heading above this chunk
    (e.g., "7. Termination Clause"), preserving structural provenance.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    Vector = None  # type: ignore[assignment]
    _PGVECTOR_AVAILABLE = False

from app.core.config import settings
from app.db.base import Base


# Embedding dimension: 768 dimensions for Google Gemini gemini-embedding-2 (DEC-024).
EMBEDDING_DIMENSION: int = settings.embedding_dimension


def _vector_column():
    """
    Returns the appropriate SQLAlchemy column type for the embedding.
    Uses pgvector.sqlalchemy.Vector(768) if available, otherwise raises RuntimeError.
    """
    if _PGVECTOR_AVAILABLE and Vector is not None:
        return Vector(EMBEDDING_DIMENSION)
    # This fallback should never reach production migration.
    raise RuntimeError(
        "pgvector Python package is required to define DocumentChunk. "
        "Install it: pip install pgvector"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this chunk",
    )

    # ----------------------------------------------------------------
    # Evidence Lineage FK → Contract
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent contract this chunk belongs to",
    )

    # ----------------------------------------------------------------
    # Location / Provenance (Critical for citations)
    # ----------------------------------------------------------------
    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1-indexed page number in the source PDF where this chunk appears",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="0-indexed position of this chunk within the page",
    )
    char_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character offset (start) of this chunk within the full extracted page text",
    )
    char_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character offset (end) of this chunk within the full extracted page text",
    )
    section_header: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Nearest document section heading above this chunk (e.g. '7. Termination')",
    )

    # ----------------------------------------------------------------
    # Content
    # ----------------------------------------------------------------
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw text content of this chunk",
    )

    # ----------------------------------------------------------------
    # Vector Embedding (pgvector — Phase 2+)
    # ----------------------------------------------------------------
    # Embedding vector for semantic similarity search.
    # Populated during the chunking/embedding pipeline (Phase 2).
    # Dimension: PENDING DEC-010 (embedding model not yet selected).
    # See module-level docstring for dimension options.
    embedding: Mapped[object | None] = mapped_column(
        _vector_column(),
        nullable=True,
        comment=(
            "Dense 768-dimensional vector embedding of chunk text. "
            "Populated via Gemini gemini-embedding-2 in Phase 4B. "
            "Indexed with HNSW (vector_cosine_ops) in Phase 4C."
        ),
    )

    # ----------------------------------------------------------------
    # Full-Text Search (Phase 3+)
    # ----------------------------------------------------------------
    # tsvector for keyword/BM25 search is best maintained as a
    # generated column in PostgreSQL; it is added via a raw SQL migration
    # in Phase 3 rather than declared here to keep the ORM model clean.

    # ----------------------------------------------------------------
    # Timestamps
    # ----------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp",
    )

    # ----------------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------------
    contract: Mapped["Contract"] = relationship(  # noqa: F821
        "Contract",
        back_populates="document_chunks",
    )
    clauses: Mapped[list["Clause"]] = relationship(  # noqa: F821
        "Clause",
        back_populates="source_chunk",
    )
    risk_signals: Mapped[list["RiskSignal"]] = relationship(  # noqa: F821
        "RiskSignal",
        back_populates="source_chunk",
    )
    obligations: Mapped[list["Obligation"]] = relationship(  # noqa: F821
        "Obligation",
        back_populates="source_chunk",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.id} "
            f"contract_id={self.contract_id} "
            f"page={self.page_number} idx={self.chunk_index}>"
        )
