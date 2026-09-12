"""
ContractIQ — Embedding Generation Service (Phase 4B)

Orchestrates vector embedding generation and database persistence for contract chunks.
Reads DocumentChunk records, submits texts to EmbeddingProvider (Gemini gemini-embedding-2),
asserts dimensionality (768), and persists dense vectors to PostgreSQL via SQLAlchemy.

Key guarantees:
  - One DocumentChunk -> One 768-dimensional embedding.
  - Strict order preservation (ordered deterministically by chunk_index ASC).
  - Idempotency: skips chunks with existing embeddings unless force_reembed=True.
  - Atomic persistence: all chunks for a contract are committed together.
  - Failure safety: rolls back on error to prevent partial/inconsistent contract state.
  - Text invariant: uses DocumentChunk.text directly without altering stored chunks.
  - Zero raw contract text or secrets logged.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.embedding import ContractEmbeddingResponse
from app.services.embedding_factory import get_embedding_provider
from app.services.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTaskType,
)

logger = logging.getLogger(__name__)


class EmbeddingGenerationError(Exception):
    """Base exception for contract embedding generation errors."""
    pass


class ContractNotFoundError(EmbeddingGenerationError):
    """Raised when the target contract does not exist."""
    pass


class NoChunksFoundError(EmbeddingGenerationError):
    """Raised when the contract has zero persisted chunks."""
    pass


async def generate_contract_embeddings(
    db: Session,
    contract_id: uuid.UUID,
    provider: Optional[EmbeddingProvider] = None,
    force_reembed: bool = False,
) -> ContractEmbeddingResponse:
    """
    Generates and persists dense vector embeddings for all chunks of a contract.

    Args:
        db: Active synchronous SQLAlchemy database session.
        contract_id: UUID of the contract.
        provider: Optional EmbeddingProvider instance (defaults to get_embedding_provider()).
        force_reembed: If True, re-generates embeddings for all chunks even if already populated.

    Returns:
        ContractEmbeddingResponse detailing total, embedded, and skipped counts.

    Raises:
        ContractNotFoundError: If contract does not exist.
        NoChunksFoundError: If contract has zero chunks.
        EmbeddingGenerationError: If provider call or database persistence fails.
    """
    # 1. Fetch target contract
    contract = db.scalars(
        select(Contract).where(Contract.id == contract_id)
    ).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # 2. Fetch all chunks ordered deterministically by chunk_index
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.contract_id == contract_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).all()
    )

    if not chunks:
        raise NoChunksFoundError(
            f"Contract '{contract_id}' has no chunks to embed. Run chunking first."
        )

    # 3. Determine which chunks need embeddings (Idempotency)
    if force_reembed:
        chunks_to_embed = chunks
        skipped_chunks = []
    else:
        chunks_to_embed = [c for c in chunks if c.embedding is None]
        skipped_chunks = [c for c in chunks if c.embedding is not None]

    # If all chunks already have embeddings and force is False, return immediately
    # Guaranteed: zero external API calls made
    if not chunks_to_embed:
        return ContractEmbeddingResponse(
            contract_id=contract.id,
            total_chunks=len(chunks),
            embedded_chunks=0,
            skipped_chunks=len(skipped_chunks),
            dimension=provider.dimension if provider else 768,
            model=provider.model_name if provider else "gemini-embedding-2",
            processing_status=contract.processing_status,
            message=(
                f"All {len(chunks)} chunks already have embeddings. "
                f"Zero embeddings generated (use force_reembed=True to re-generate)."
            ),
        )

    # 4. Resolve embedding provider
    if provider is None:
        try:
            provider = get_embedding_provider()
        except EmbeddingConfigurationError as exc:
            raise EmbeddingGenerationError(
                f"Failed to initialize embedding provider: {exc}"
            ) from exc

    # 5. Extract chunk texts preserving strict index ordering
    texts_to_embed = [c.text for c in chunks_to_embed]

    # 6. Generate embeddings via provider
    try:
        vectors = await provider.embed_texts(
            texts=texts_to_embed,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
            title=contract.title,
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "Embedding generation provider call failed for contract %s (%d chunks): %s",
            contract_id,
            len(texts_to_embed),
            type(exc).__name__,
        )
        raise EmbeddingGenerationError(
            f"Embedding generation failed during provider call: {type(exc).__name__}: {exc}"
        ) from exc

    # 7. Validate N -> N mapping and vector dimensionality
    if len(vectors) != len(chunks_to_embed):
        db.rollback()
        raise EmbeddingGenerationError(
            f"Embedding count mismatch: sent {len(chunks_to_embed)} chunks, "
            f"received {len(vectors)} vectors from provider."
        )

    for idx, (chunk, vec) in enumerate(zip(chunks_to_embed, vectors)):
        if not isinstance(vec, list) or len(vec) != provider.dimension:
            db.rollback()
            actual_len = len(vec) if isinstance(vec, list) else "not a list"
            raise EmbeddingGenerationError(
                f"Dimensionality validation failed for chunk index {chunk.chunk_index}: "
                f"expected {provider.dimension} dimensions, received {actual_len}."
            )
        chunk.embedding = vec

    # 8. Persist atomically in single commit
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(
            "Database commit failed during embedding persistence for contract %s: %s",
            contract_id,
            type(exc).__name__,
        )
        raise EmbeddingGenerationError(
            f"Database commit failed while persisting chunk embeddings: {exc}"
        ) from exc

    return ContractEmbeddingResponse(
        contract_id=contract.id,
        total_chunks=len(chunks),
        embedded_chunks=len(chunks_to_embed),
        skipped_chunks=len(skipped_chunks),
        dimension=provider.dimension,
        model=provider.model_name,
        processing_status=contract.processing_status,
        message=(
            f"Successfully generated and persisted {len(chunks_to_embed)} embeddings "
            f"({provider.dimension} dimensions, model '{provider.model_name}') for contract. "
            f"Skipped {len(skipped_chunks)} already-embedded chunks."
        ),
    )
