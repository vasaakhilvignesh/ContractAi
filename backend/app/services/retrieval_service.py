"""
ContractIQ — Semantic Vector Retrieval Service (Phase 5A)

Orchestrates vector similarity search over document chunks for a specific contract.
Uses Gemini gemini-embedding-2 (RETRIEVAL_QUERY task type) to produce a 768-dimensional
dense query vector, executes a pgvector cosine-distance query (<=>) ordered by distance ascending,
and returns ranked ChunkMatch results.

Guarantees:
  - Contract-scoped: only chunks belonging to the specified contract are retrieved.
  - Zero RAG / generation: returns ranked chunks only, no LLM answers or citations.
  - Precise distance/similarity: returns raw cosine distance and calculated similarity score.
  - No NULL embeddings: filters out chunks with unpopulated embeddings.
  - Safe bounds: respects top_k (1-20) and optional min_similarity threshold.
  - Zero sensitive data or credentials logged.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.query import ChunkMatch, ContractQueryResponse
from app.services.embedding_factory import get_embedding_provider
from app.services.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderError,
)

logger = logging.getLogger(__name__)


class RetrievalError(Exception):
    """Base exception for retrieval errors."""
    pass


class ContractNotFoundError(RetrievalError):
    """Raised when the requested contract does not exist."""
    pass


class NoChunksFoundError(RetrievalError):
    """Raised when the contract has zero document chunks."""
    pass


class NoEmbeddedChunksError(RetrievalError):
    """Raised when the contract has document chunks but none have embeddings."""
    pass


async def query_contract_chunks(
    db: Session,
    contract_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    min_similarity: Optional[float] = None,
    provider: Optional[EmbeddingProvider] = None,
) -> ContractQueryResponse:
    """
    Executes semantic vector retrieval against the chunks of a specific contract.

    Args:
        db: Active synchronous SQLAlchemy session.
        contract_id: UUID of the target contract.
        query: Validated natural language query string.
        top_k: Maximum number of ranked chunks to return (default 5, range 1-20).
        min_similarity: Optional minimum similarity threshold in [0.0, 1.0].
        provider: Optional EmbeddingProvider instance (defaults to get_embedding_provider()).

    Returns:
        ContractQueryResponse containing ranked ChunkMatch items.

    Raises:
        ContractNotFoundError: If contract does not exist.
        NoChunksFoundError: If contract has 0 chunks.
        NoEmbeddedChunksError: If contract has chunks but 0 embeddings.
        RetrievalError: If embedding generation or query execution fails.
    """
    # 1. Validate contract existence
    contract = db.scalars(
        select(Contract).where(Contract.id == contract_id)
    ).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # 2. Validate that chunks exist for this contract
    total_chunk_count = db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.contract_id == contract_id)
    ) or 0
    if total_chunk_count == 0:
        raise NoChunksFoundError(
            f"Contract '{contract_id}' has no chunks. Run chunking first."
        )

    # 3. Validate that embedded chunks exist for this contract
    embedded_chunk_count = db.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.contract_id == contract_id,
            DocumentChunk.embedding.is_not(None),
        )
    ) or 0
    if embedded_chunk_count == 0:
        raise NoEmbeddedChunksError(
            f"Contract '{contract_id}' has no embedded chunks. Run embedding generation first."
        )

    # 4. Resolve embedding provider
    if provider is None:
        try:
            provider = get_embedding_provider()
        except EmbeddingConfigurationError as exc:
            raise RetrievalError(
                f"Failed to initialize embedding provider: {exc}"
            ) from exc

    # 5. Generate query embedding (RETRIEVAL_QUERY, 768 dimensions)
    try:
        query_vector = await provider.embed_query(query)
    except Exception as exc:
        logger.error(
            "Query embedding generation failed for contract %s: %s",
            contract_id,
            type(exc).__name__,
        )
        raise RetrievalError(
            f"Query embedding generation failed: {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(query_vector, list) or len(query_vector) != provider.dimension:
        raise RetrievalError(
            f"Query embedding dimensionality mismatch: expected {provider.dimension}, "
            f"received {len(query_vector) if isinstance(query_vector, list) else 'non-list'}."
        )

    # 6. Build and execute pgvector cosine-distance query
    # operator: <=> (vector_cosine_ops)
    distance_expr = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")

    stmt = (
        select(DocumentChunk, distance_expr)
        .where(
            DocumentChunk.contract_id == contract_id,
            DocumentChunk.embedding.is_not(None),
        )
    )

    # Apply optional minimum similarity threshold (similarity >= min_sim <=> distance <= 1.0 - min_sim)
    if min_similarity is not None:
        max_distance = 1.0 - min_similarity
        stmt = stmt.where(distance_expr <= max_distance)

    # Order nearest chunks first (cosine distance ascending)
    stmt = stmt.order_by(distance_expr.asc()).limit(top_k)

    try:
        results = db.execute(stmt).all()
    except Exception as exc:
        logger.error(
            "Database vector query failed for contract %s: %s",
            contract_id,
            type(exc).__name__,
        )
        raise RetrievalError(
            f"Database vector similarity query failed: {exc}"
        ) from exc

    # 7. Transform database records into ChunkMatch schemas
    matches: list[ChunkMatch] = []
    for chunk, raw_distance in results:
        dist = float(raw_distance)
        sim = float(1.0 - dist)
        matches.append(
            ChunkMatch(
                id=chunk.id,
                contract_id=chunk.contract_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                section_header=chunk.section_header,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                similarity_score=round(sim, 6),
                cosine_distance=round(dist, 6),
            )
        )

    return ContractQueryResponse(
        contract_id=contract.id,
        query=query,
        total_matches=len(matches),
        top_k=top_k,
        min_similarity=min_similarity,
        matches=matches,
    )
