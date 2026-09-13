"""
ContractIQ — Grounded RAG & Citation Schemas (Phase 9A–9E)

Defines Pydantic v2 schemas for:
  - 9A: Context Construction & Query Requests
  - 9B: Grounded LLM Response Structure (LLM extraction schema)
  - 9C: Citation & Evidence Lineage
  - 9D: Citation Validation Results
  - 9E: Grounded Answer & Not-Found / Insufficient-Evidence Responses
"""

from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class RAGStatus(str, Enum):
    """Execution status of the Grounded RAG query."""
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_RETRIEVAL_MATCHES = "no_retrieval_matches"
    LOW_RETRIEVAL_CONFIDENCE = "low_retrieval_confidence"


class CitationVerificationStatus(str, Enum):
    """Validation status for a cited evidence source."""
    VALID = "valid"
    TEXT_MISMATCH = "text_mismatch"
    PAGE_MISMATCH = "page_mismatch"
    CHUNK_NOT_FOUND = "chunk_not_found"
    WRONG_CONTRACT = "wrong_contract"
    UNVERIFIED = "unverified"


# ====================================================================
# Request Schema
# ====================================================================

class RAGQueryRequest(BaseModel):
    """Request payload for grounded contract question-answering."""
    query: str = Field(
        ...,
        min_length=2,
        max_length=2000,
        description="Natural language question about the contract.",
        examples=["What is the notice period required for termination?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Number of chunks to retrieve for context window.",
    )
    min_score_threshold: Optional[float] = Field(
        default=0.005,
        ge=0.0,
        description="Minimum RRF hybrid retrieval score to consider evidence relevant.",
    )

    model_config = ConfigDict(from_attributes=True)


# ====================================================================
# Citation & Lineage Schemas (Phase 9C & 9D)
# ====================================================================

class RAGCitation(BaseModel):
    """
    Structured evidence citation supporting a claim in the answer:
    answer → claim → citation → chunk → page → contract.
    """
    contract_id: uuid.UUID = Field(
        ...,
        description="Parent contract UUID.",
    )
    chunk_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the referenced document chunk.",
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-indexed source PDF page number.",
    )
    section_header: Optional[str] = Field(
        default=None,
        description="Document section header where citation was extracted.",
    )
    verbatim_quote: str = Field(
        ...,
        description="Verbatim excerpt from contract text proving the claim.",
    )
    verification_status: CitationVerificationStatus = Field(
        default=CitationVerificationStatus.UNVERIFIED,
        description="Deterministic verification status against database chunk.",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Explanation of verification outcome or mismatch reason.",
    )


class AnswerClaim(BaseModel):
    """An individual atomic factual claim with supporting citations."""
    claim_text: str = Field(
        ...,
        description="Specific factual proposition made in the answer.",
    )
    citations: list[RAGCitation] = Field(
        default_factory=list,
        description="Citations supporting this factual proposition.",
    )
    is_grounded: bool = Field(
        default=True,
        description="True if claim is supported by verified citations.",
    )


# ====================================================================
# LLM Structured Output Schemas (Phase 9B)
# ====================================================================

class LLMCitationItem(BaseModel):
    """Raw citation item emitted by the LLM."""
    chunk_id: Optional[str] = Field(
        default=None,
        description="UUID or index of referenced chunk as provided in context.",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page number from referenced chunk.",
    )
    verbatim_quote: str = Field(
        ...,
        description="Exact quote from the provided context supporting this claim.",
    )


class LLMClaimItem(BaseModel):
    """Raw claim item emitted by the LLM."""
    claim: str = Field(
        ...,
        description="Factual claim made in the answer.",
    )
    citations: list[LLMCitationItem] = Field(
        default_factory=list,
        description="Citations from context supporting this claim.",
    )


class StructuredRAGAnswerLLM(BaseModel):
    """
    Schema for structured LLM answer generation via StructuredLLMProvider.
    Enforces strict grounding, citation attribution, and not-found flagging.
    """
    has_sufficient_evidence: bool = Field(
        ...,
        description="True if context contains clear evidence to answer the query; False if absent or ambiguous.",
    )
    answer: str = Field(
        ...,
        description="Direct, grounded answer synthesized exclusively from context, or clear insufficient-evidence explanation.",
    )
    claims: list[LLMClaimItem] = Field(
        default_factory=list,
        description="List of atomic claims and citations supporting the answer.",
    )


# ====================================================================
# Full Response Schema (Phase 9E)
# ====================================================================

class RAGQueryResponse(BaseModel):
    """Complete grounded RAG query response."""
    contract_id: uuid.UUID
    query: str
    status: RAGStatus
    answer: str
    has_sufficient_evidence: bool
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in retrieval and evidence grounding.",
    )
    claims: list[AnswerClaim] = Field(
        default_factory=list,
        description="Breakdown of factual claims and validated citations.",
    )
    total_chunks_retrieved: int = 0
    total_citations: int = 0
    valid_citations_count: int = 0
    invalid_citations_count: int = 0

    model_config = ConfigDict(from_attributes=True)
