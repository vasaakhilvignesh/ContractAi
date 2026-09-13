"""
ContractIQ — Analyst API Schemas (Phase 10A–10E)

Defines Pydantic v2 schemas for:
  - 10A: Analyst API Foundation & Error Responses
  - 10B: Single-Contract Analysis Requests & Responses
  - 10C: Cross-Contract Multi-Document Analysis Requests & Responses
  - 10D: Evidence-Backed Claims with Full Lineage Trace
  - 10E: Retrieval & Debug Metadata (selected chunks, scoring, provenance, zero secrets/embeddings)
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rag import (
    AnswerClaim,
    CitationVerificationStatus,
    RAGCitation,
    RAGStatus,
)


class AnalystQueryScope(str, Enum):
    """Scope of the analyst query."""
    SINGLE_CONTRACT = "single_contract"
    CROSS_CONTRACT = "cross_contract"


# ====================================================================
# Phase 10E: Retrieval & Debug Metadata Schemas
# ====================================================================

class ChunkDebugInfo(BaseModel):
    """
    Debug metadata for an individual retrieved chunk.
    Exposes retrieval ranks, scores, and provenance WITHOUT embeddings or secrets.
    """
    chunk_id: uuid.UUID = Field(..., description="Unique chunk identifier.")
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID.")
    contract_title: Optional[str] = Field(default=None, description="Contract title for scoping.")
    page_number: int = Field(..., description="1-indexed source PDF page number.")
    chunk_index: int = Field(..., description="Sequence index within contract.")
    section_header: Optional[str] = Field(default=None, description="Nearest section heading.")
    char_length: int = Field(..., description="Character length of chunk text.")
    hybrid_score: float = Field(..., description="Fused RRF score.")
    semantic_rank: Optional[int] = Field(default=None, description="Rank from semantic vector search.")
    semantic_similarity: Optional[float] = Field(default=None, description="Cosine similarity score.")
    keyword_rank: Optional[int] = Field(default=None, description="Rank from keyword FTS.")
    keyword_score: Optional[float] = Field(default=None, description="PostgreSQL ts_rank_cd score.")

    model_config = ConfigDict(from_attributes=True)


class RetrievalDebugInfo(BaseModel):
    """
    Comprehensive retrieval and debug provenance.
    Included only when include_debug=True is requested.
    """
    retrieval_method: str = Field(
        default="hybrid_rrf",
        description="Retrieval strategy used (e.g. 'hybrid_rrf', 'cross_contract_hybrid_rrf').",
    )
    total_contracts_searched: int = Field(
        default=1,
        ge=1,
        description="Number of contracts queried in this execution.",
    )
    contract_ids_queried: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of contract UUIDs searched.",
    )
    total_chunks_considered: int = Field(
        default=0,
        ge=0,
        description="Total chunks retrieved across all searched contracts.",
    )
    selected_chunks: list[ChunkDebugInfo] = Field(
        default_factory=list,
        description="Ordered list of chunks injected into context with ranking metrics.",
    )
    context_char_count: int = Field(
        default=0,
        ge=0,
        description="Total characters in the constructed LLM context window.",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Model name/version of the structured LLM provider.",
    )
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="Total pipeline execution time in milliseconds.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Phase 10D: Evidence-Backed Citation Schemas
# ====================================================================

class AnalystEvidenceCitation(BaseModel):
    """
    Rich evidence citation preserving full 6-tier lineage:
    answer → claim → evidence → chunk → page → contract.
    """
    contract_id: uuid.UUID = Field(..., description="Parent contract UUID.")
    contract_title: Optional[str] = Field(default=None, description="Contract title for cross-contract context.")
    chunk_id: Optional[uuid.UUID] = Field(default=None, description="Referenced chunk UUID.")
    page_number: Optional[int] = Field(default=None, ge=1, description="Source PDF page number.")
    section_header: Optional[str] = Field(default=None, description="Section heading.")
    verbatim_quote: str = Field(..., description="Exact quote from contract text.")
    verification_status: CitationVerificationStatus = Field(
        default=CitationVerificationStatus.UNVERIFIED,
        description="Deterministic verification outcome against database chunk.",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Explanation of verification outcome or mismatch details.",
    )
    evidence_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Associated persistent Evidence model UUID if linked.",
    )

    model_config = ConfigDict(from_attributes=True)


class AnalystAnswerClaim(BaseModel):
    """Atomic answer claim with attached citations."""
    claim_text: str = Field(..., description="Factual proposition made in the answer.")
    contract_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Contract to which this specific claim applies (essential for cross-contract).",
    )
    citations: list[AnalystEvidenceCitation] = Field(
        default_factory=list,
        description="Evidence citations supporting this claim.",
    )
    is_grounded: bool = Field(
        default=True,
        description="True if claim is supported by at least one valid verified citation.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Phase 10B & 10C: Request Payloads
# ====================================================================

class SingleContractAnalystRequest(BaseModel):
    """Request payload for asking a question against a single contract (Phase 10B)."""
    query: str = Field(
        ...,
        min_length=2,
        max_length=2000,
        description="Natural language question about the contract.",
        examples=["What are the termination notice requirements?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve for the context window.",
    )
    min_score_threshold: Optional[float] = Field(
        default=0.005,
        ge=0.0,
        description="Minimum RRF hybrid retrieval score threshold.",
    )
    include_debug: bool = Field(
        default=False,
        description="Whether to include retrieval and debug metadata in the response.",
    )

    model_config = ConfigDict(from_attributes=True)


class CrossContractAnalystRequest(BaseModel):
    """Request payload for asking questions across multiple contracts (Phase 10C)."""
    contract_ids: list[uuid.UUID] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of 2 to 10 contract UUIDs to compare or query across.",
    )
    query: str = Field(
        ...,
        min_length=2,
        max_length=2000,
        description="Comparative or multi-contract question.",
        examples=["Compare the limitation of liability across both contracts."],
    )
    top_k_per_contract: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Number of chunks to retrieve per contract.",
    )
    min_score_threshold: Optional[float] = Field(
        default=0.005,
        ge=0.0,
        description="Minimum RRF hybrid retrieval score threshold.",
    )
    include_debug: bool = Field(
        default=False,
        description="Whether to include retrieval and debug metadata in the response.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Response Schemas (Phase 10B, 10C, 10D, 10E)
# ====================================================================

class AnalystQueryResponse(BaseModel):
    """
    Unified response payload for ContractIQ Analyst queries.
    Used for both single-contract and cross-contract questions.
    """
    scope: AnalystQueryScope = Field(
        ...,
        description="Query scope: single_contract or cross_contract.",
    )
    contract_ids: list[uuid.UUID] = Field(
        ...,
        description="UUID(s) of the contracts evaluated.",
    )
    query: str = Field(..., description="Original user question.")
    status: RAGStatus = Field(
        ...,
        description="Execution status: answered, insufficient_evidence, no_retrieval_matches, low_retrieval_confidence.",
    )
    answer: str = Field(
        ...,
        description="Synthesized evidence-backed answer or safe not-found explanation.",
    )
    has_sufficient_evidence: bool = Field(
        ...,
        description="True if context contains adequate evidence to answer the question.",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score based on retrieval scores and citation verification.",
    )
    claims: list[AnalystAnswerClaim] = Field(
        default_factory=list,
        description="Atomic factual claims with validated citations and lineage.",
    )
    total_chunks_retrieved: int = Field(
        default=0,
        ge=0,
        description="Total chunks retrieved across all queried contracts.",
    )
    total_citations: int = Field(
        default=0,
        ge=0,
        description="Total citations cited in the answer.",
    )
    valid_citations_count: int = Field(
        default=0,
        ge=0,
        description="Count of citations deterministically verified as valid.",
    )
    invalid_citations_count: int = Field(
        default=0,
        ge=0,
        description="Count of citations that failed verification.",
    )
    debug_info: Optional[RetrievalDebugInfo] = Field(
        default=None,
        description="Optional retrieval and scoring debug information (omitted unless requested).",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of answer generation.",
    )

    model_config = ConfigDict(from_attributes=True)
