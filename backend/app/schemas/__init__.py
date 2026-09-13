"""
ContractIQ — Schemas Package
"""

from app.schemas.health import DatabaseHealthSchema, HealthResponseSchema
from app.schemas.contract import (
    ContractBase,
    ContractCreate,
    ContractUpdate,
    ContractResponse,
    ContractListResponse,
    ContractUploadResponse,
    ProcessingStatus,
    ContractProcessingStatusUpdate,
    ContractProcessingStatusResponse,
)

from app.schemas.extraction import (
    PageBlock,
    PageExtraction,
    ExtractionResult,
    ContractExtractionResponse,
)

from app.schemas.chunk import (
    ChunkBase,
    ChunkCreate,
    ChunkResponse,
    ContractChunkingResponse,
    ContractChunkListResponse,
    DocumentChunkSummary,
)

from app.schemas.embedding import (
    ContractEmbedRequest,
    ContractEmbeddingResponse,
)

from app.schemas.query import (
    ContractQueryRequest,
    ChunkMatch,
    ContractQueryResponse,
    ContractKeywordQueryRequest,
    KeywordChunkMatch,
    ContractKeywordQueryResponse,
    ContractHybridQueryRequest,
    HybridChunkMatch,
    ContractHybridQueryResponse,
)

from app.schemas.clause import (
    ClauseType,
    ExtractedClauseLLM,
    ChunkClauseExtractionResult,
    ClauseBase,
    ClauseResponse,
    ContractClauseExtractionRequest,
    ContractClauseExtractionResponse,
    ContractClauseListResponse,
)

from app.schemas.obligation import (
    ObligationType,
    ExtractedObligationLLM,
    ClauseObligationExtractionResult,
    ObligationBase,
    ObligationResponse,
    ContractObligationExtractionRequest,
    ContractObligationExtractionResponse,
    ContractObligationListResponse,
)

__all__ = [
    "DatabaseHealthSchema",
    "HealthResponseSchema",
    "ContractBase",
    "ContractCreate",
    "ContractUpdate",
    "ContractResponse",
    "ContractListResponse",
    "ContractUploadResponse",
    "ProcessingStatus",
    "ContractProcessingStatusUpdate",
    "ContractProcessingStatusResponse",
    "PageBlock",
    "PageExtraction",
    "ExtractionResult",
    "ContractExtractionResponse",
    "ChunkBase",
    "ChunkCreate",
    "ChunkResponse",
    "ContractChunkingResponse",
    "ContractChunkListResponse",
    "DocumentChunkSummary",
    "ContractEmbedRequest",
    "ContractEmbeddingResponse",
    "ContractQueryRequest",
    "ChunkMatch",
    "ContractQueryResponse",
    "ContractKeywordQueryRequest",
    "KeywordChunkMatch",
    "ContractKeywordQueryResponse",
    "ContractHybridQueryRequest",
    "HybridChunkMatch",
    "ContractHybridQueryResponse",
    "ClauseType",
    "ExtractedClauseLLM",
    "ChunkClauseExtractionResult",
    "ClauseBase",
    "ClauseResponse",
    "ContractClauseExtractionRequest",
    "ContractClauseExtractionResponse",
    "ContractClauseListResponse",
    "ObligationType",
    "ExtractedObligationLLM",
    "ClauseObligationExtractionResult",
    "ObligationBase",
    "ObligationResponse",
    "ContractObligationExtractionRequest",
    "ContractObligationExtractionResponse",
    "ContractObligationListResponse",
]
