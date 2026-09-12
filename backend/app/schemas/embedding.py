"""
ContractIQ — Embedding Schemas (Phase 4B)

Pydantic schemas for contract embedding operations.
"""

import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ContractEmbedRequest(BaseModel):
    """Request payload for embedding generation."""

    force_reembed: bool = Field(
        default=False,
        description=(
            "If True, re-generates embeddings for all chunks even if an embedding "
            "vector already exists. If False (default), skips already-embedded chunks."
        ),
        examples=[False],
    )

    model_config = ConfigDict(from_attributes=True)


class ContractEmbeddingResponse(BaseModel):
    """Response payload after embedding generation."""

    contract_id: uuid.UUID = Field(
        ...,
        description="UUID of the contract whose chunks were embedded",
    )
    total_chunks: int = Field(
        ...,
        ge=0,
        description="Total number of DocumentChunk records belonging to this contract",
    )
    embedded_chunks: int = Field(
        ...,
        ge=0,
        description="Number of chunks for which embeddings were newly generated in this request",
    )
    skipped_chunks: int = Field(
        ...,
        ge=0,
        description="Number of chunks that already had embeddings and were skipped (idempotency)",
    )
    dimension: int = Field(
        default=768,
        description="Dimensionality of the dense vectors (768 for gemini-embedding-2)",
    )
    model: str = Field(
        default="gemini-embedding-2",
        description="Embedding model name used for vector generation",
    )
    processing_status: str = Field(
        ...,
        description="Current document processing lifecycle status of the contract",
    )
    message: str = Field(
        ...,
        description="Human-readable execution outcome summary",
    )

    model_config = ConfigDict(from_attributes=True)
