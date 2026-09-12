"""
ContractIQ — Document Chunk Schemas (Phase 3B)

Pydantic v2 schemas for:
  - DocumentChunk representation and serialization
  - Chunk creation and persistence models
  - Chunking pipeline response summaries
  - Paginated chunk listing
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChunkBase(BaseModel):
    """Base fields shared across chunk schemas."""

    page_number: int = Field(
        ..., ge=1, description="1-indexed source PDF page number where this chunk appears"
    )
    chunk_index: int = Field(
        ..., ge=0, description="0-indexed global sequence position within the contract document"
    )
    char_start: Optional[int] = Field(
        default=None,
        ge=0,
        description="Character start offset of this chunk within the normalized page text",
    )
    char_end: Optional[int] = Field(
        default=None,
        ge=0,
        description="Character end offset of this chunk within the normalized page text",
    )
    section_header: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Nearest governing section heading above this chunk",
    )
    text: str = Field(..., min_length=1, description="Verbatim normalized text content of the chunk")


class ChunkCreate(ChunkBase):
    """Payload for creating a new DocumentChunk in the database."""

    contract_id: uuid.UUID = Field(..., description="Parent contract UUID")


class ChunkResponse(ChunkBase):
    """Full representation of a persisted DocumentChunk."""

    id: uuid.UUID = Field(..., description="Unique UUID for this chunk")
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID")
    created_at: datetime = Field(..., description="Timestamp when the chunk was created")

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkSummary(BaseModel):
    """Compact summary of a chunk suitable for preview and sample listings."""

    id: uuid.UUID = Field(..., description="Unique UUID for this chunk")
    page_number: int = Field(..., description="Source page number")
    chunk_index: int = Field(..., description="Global chunk index")
    section_header: Optional[str] = Field(default=None, description="Governing section header")
    text_snippet: str = Field(..., description="Preview snippet of the chunk text")
    char_count: int = Field(..., description="Length of the chunk text in characters")

    model_config = ConfigDict(from_attributes=True)


class ContractChunkingResponse(BaseModel):
    """Response returned by POST /contracts/{contract_id}/chunk."""

    contract_id: uuid.UUID = Field(..., description="Parent contract UUID")
    total_chunks: int = Field(..., ge=0, description="Total number of chunks produced and persisted")
    total_pages: int = Field(..., ge=0, description="Total pages processed from source PDF")
    processing_status: str = Field(..., description="Lifecycle status of the contract")
    sample_chunks: list[DocumentChunkSummary] = Field(
        default_factory=list, description="Sample preview of initial chunks"
    )
    message: Optional[str] = Field(default=None, description="Human-readable result summary")

    model_config = ConfigDict(from_attributes=True)


class ContractChunkListResponse(BaseModel):
    """Paginated list of document chunks for a contract."""

    items: list[ChunkResponse] = Field(..., description="List of chunk items")
    total: int = Field(..., ge=0, description="Total chunk count for this contract")
    limit: int = Field(..., ge=1, description="Page limit applied")
    offset: int = Field(..., ge=0, description="Offset applied")

    model_config = ConfigDict(from_attributes=True)
