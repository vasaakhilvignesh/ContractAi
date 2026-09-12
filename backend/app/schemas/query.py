"""
ContractIQ — Semantic Retrieval Schemas (Phase 5A)

Pydantic v2 schemas for:
  - ContractQueryRequest: search query, top_k, and optional min_similarity threshold
  - ChunkMatch: ranked matching document chunk with similarity score and location metadata
  - ContractQueryResponse: complete vector retrieval response
"""

import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractQueryRequest(BaseModel):
    """Request payload for semantic vector search within a contract."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query for semantic retrieval",
        examples=["What is the notice period for early termination?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of nearest document chunks to return (1-20)",
        examples=[5],
    )
    min_similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional minimum cosine similarity threshold [0.0, 1.0]",
        examples=[0.65],
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_whitespace(cls, v: str) -> str:
        """Reject empty or whitespace-only query strings."""
        if not v or not v.strip():
            raise ValueError("Query text must not be empty or whitespace only.")
        return v.strip()

    model_config = ConfigDict(from_attributes=True)


class ChunkMatch(BaseModel):
    """A single document chunk match returned by semantic vector search."""

    id: uuid.UUID = Field(..., description="Unique chunk identifier")
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID")
    page_number: int = Field(..., description="1-indexed source PDF page number")
    chunk_index: int = Field(..., description="0-indexed global chunk sequence index")
    section_header: Optional[str] = Field(
        default=None,
        description="Nearest governing section heading above this chunk",
    )
    text: str = Field(..., description="Verbatim text content of the chunk")
    char_start: Optional[int] = Field(
        default=None,
        description="Start character offset within the normalized page text",
    )
    char_end: Optional[int] = Field(
        default=None,
        description="End character offset within the normalized page text",
    )
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score calculated as (1.0 - cosine_distance)",
    )
    cosine_distance: float = Field(
        ...,
        description="Raw pgvector cosine distance (0.0 = identical, 1.0 = orthogonal)",
    )

    model_config = ConfigDict(from_attributes=True)


class ContractQueryResponse(BaseModel):
    """Response payload for semantic vector search."""

    contract_id: uuid.UUID = Field(..., description="UUID of the searched contract")
    query: str = Field(..., description="Original query string")
    total_matches: int = Field(..., ge=0, description="Total number of matches returned")
    top_k: int = Field(..., ge=1, le=20, description="Requested top_k limit")
    min_similarity: Optional[float] = Field(
        default=None,
        description="Applied minimum similarity threshold, if any",
    )
    matches: list[ChunkMatch] = Field(
        default_factory=list,
        description="Ranked list of matching document chunks ordered by similarity descending",
    )

    model_config = ConfigDict(from_attributes=True)


class ContractKeywordQueryRequest(BaseModel):
    """Request payload for keyword full-text search within a contract."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Search query for keyword full-text retrieval",
        examples=["indemnification liability notice"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of nearest document chunks to return (1-20)",
        examples=[5],
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_whitespace(cls, v: str) -> str:
        """Reject empty or whitespace-only query strings."""
        if not v or not v.strip():
            raise ValueError("Query text must not be empty or whitespace only.")
        return v.strip()

    model_config = ConfigDict(from_attributes=True)


class KeywordChunkMatch(BaseModel):
    """A single document chunk match returned by keyword full-text search."""

    id: uuid.UUID = Field(..., description="Unique chunk identifier")
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID")
    page_number: int = Field(..., description="1-indexed source PDF page number")
    chunk_index: int = Field(..., description="0-indexed global chunk sequence index")
    section_header: Optional[str] = Field(
        default=None,
        description="Nearest governing section heading above this chunk",
    )
    text: str = Field(..., description="Verbatim text content of the chunk")
    char_start: Optional[int] = Field(
        default=None,
        description="Start character offset within the normalized page text",
    )
    char_end: Optional[int] = Field(
        default=None,
        description="End character offset within the normalized page text",
    )
    keyword_rank: float = Field(
        ...,
        description="PostgreSQL Full-Text Search relevance score calculated via ts_rank_cd",
    )

    model_config = ConfigDict(from_attributes=True)


class ContractKeywordQueryResponse(BaseModel):
    """Response payload for keyword full-text search."""

    contract_id: uuid.UUID = Field(..., description="UUID of the searched contract")
    query: str = Field(..., description="Original query string")
    total_matches: int = Field(..., ge=0, description="Total number of matches returned")
    top_k: int = Field(..., ge=1, le=20, description="Requested top_k limit")
    matches: list[KeywordChunkMatch] = Field(
        default_factory=list,
        description="Ranked list of matching document chunks ordered by keyword relevance descending",
    )

    model_config = ConfigDict(from_attributes=True)


class ContractHybridQueryRequest(BaseModel):
    """Request payload for hybrid (semantic + keyword) retrieval with RRF."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query for hybrid retrieval",
        examples=["What is the notice period for early termination?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of nearest document chunks to return (1-20)",
        examples=[5],
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        description="Reciprocal Rank Fusion smoothing parameter k (default 60)",
        examples=[60],
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_whitespace(cls, v: str) -> str:
        """Reject empty or whitespace-only query strings."""
        if not v or not v.strip():
            raise ValueError("Query text must not be empty or whitespace only.")
        return v.strip()

    model_config = ConfigDict(from_attributes=True)


class HybridChunkMatch(BaseModel):
    """A single document chunk match returned by hybrid retrieval fused with RRF."""

    id: uuid.UUID = Field(..., description="Unique chunk identifier")
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID")
    page_number: int = Field(..., description="1-indexed source PDF page number")
    chunk_index: int = Field(..., description="0-indexed global chunk sequence index")
    section_header: Optional[str] = Field(
        default=None,
        description="Nearest governing section heading above this chunk",
    )
    text: str = Field(..., description="Verbatim text content of the chunk")
    char_start: Optional[int] = Field(
        default=None,
        description="Start character offset within the normalized page text",
    )
    char_end: Optional[int] = Field(
        default=None,
        description="End character offset within the normalized page text",
    )
    hybrid_score: float = Field(
        ...,
        description="Unified Reciprocal Rank Fusion (RRF) score: sum of 1 / (k + rank)",
    )
    rrf_score: float = Field(
        ...,
        description="Reciprocal Rank Fusion score (identical to hybrid_score)",
    )
    semantic_rank: Optional[int] = Field(
        default=None,
        description="1-based rank from semantic vector retrieval, or None if not matched",
    )
    semantic_similarity: Optional[float] = Field(
        default=None,
        description="Cosine similarity score from semantic retrieval [0.0, 1.0], or None",
    )
    keyword_rank: Optional[int] = Field(
        default=None,
        description="1-based rank from keyword full-text retrieval, or None if not matched",
    )
    keyword_score: Optional[float] = Field(
        default=None,
        description="PostgreSQL Full-Text Search ts_rank_cd score, or None if not matched",
    )

    model_config = ConfigDict(from_attributes=True)


class ContractHybridQueryResponse(BaseModel):
    """Response payload for hybrid retrieval with RRF."""

    contract_id: uuid.UUID = Field(..., description="UUID of the searched contract")
    query: str = Field(..., description="Original query string")
    total_matches: int = Field(..., ge=0, description="Total number of matches returned")
    top_k: int = Field(..., ge=1, le=20, description="Requested top_k limit")
    rrf_k: int = Field(..., ge=1, description="RRF k parameter used")
    semantic_matches_count: int = Field(
        ..., ge=0, description="Count of candidate chunks retrieved via semantic search"
    )
    keyword_matches_count: int = Field(
        ..., ge=0, description="Count of candidate chunks retrieved via keyword search"
    )
    matches: list[HybridChunkMatch] = Field(
        default_factory=list,
        description="Ranked list of matching document chunks ordered by hybrid_score descending",
    )

    model_config = ConfigDict(from_attributes=True)
