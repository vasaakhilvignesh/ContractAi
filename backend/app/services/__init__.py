"""
ContractIQ — Services Package
"""

from app.services.contract_service import (
    create_contract,
    get_contract,
    list_contracts,
    update_contract,
    delete_contract,
    associate_contract_file,
    update_contract_processing_status,
    VALID_PROCESSING_TRANSITIONS,
)

from app.services.storage_service import (
    validate_pdf_upload,
    save_contract_file,
    remove_stored_file,
    sanitize_filename,
)

from app.services.pdf_extraction_service import (
    PDFExtractionError,
    PDFNotFoundError,
    PDFPathTraversalError,
    PDFEncryptedError,
    PDFCorruptedError,
    PDFPageLimitExceededError,
    resolve_pdf_path,
    extract_text_from_pdf,
    extract_contract_document,
)

from app.services.text_normalization_service import (
    normalize_text,
    is_noise_text,
)

from app.services.chunking_service import (
    ChunkingError,
    ScannedDocumentChunkingError,
    EmptyDocumentChunkingError,
    is_heading_line,
    chunk_page_text,
    chunk_extraction_result,
    persist_contract_chunks,
    list_contract_chunks,
)

from app.services.embedding_provider import (
    EmbeddingProvider,
    EmbeddingTaskType,
    EmbeddingError,
    EmbeddingConfigurationError,
    EmbeddingValidationError,
    EmbeddingProviderError,
)

from app.services.gemini_embedding_provider import GeminiEmbeddingProvider
from app.services.embedding_factory import get_embedding_provider

from app.services.embedding_generation_service import (
    EmbeddingGenerationError,
    ContractNotFoundError,
    NoChunksFoundError,
    generate_contract_embeddings,
)

from app.services.retrieval_service import (
    RetrievalError,
    NoEmbeddedChunksError,
    query_contract_chunks,
)

from app.services.keyword_retrieval_service import (
    KeywordRetrievalError,
    query_contract_keywords,
)

from app.services.hybrid_retrieval_service import (
    DEFAULT_RRF_K,
    HybridRetrievalError,
    compute_rrf_score,
    reciprocal_rank_fusion,
    query_contract_hybrid,
)

from app.services.structured_output_validator import (
    StructuredOutputError,
    StructuredOutputConfigurationError,
    StructuredOutputProviderError,
    StructuredOutputParseError,
    StructuredOutputValidationError,
    clean_json_text,
    validate_structured_output,
)

from app.services.structured_output_provider import (
    StructuredLLMProvider,
)

from app.services.gemini_structured_output_provider import (
    GeminiStructuredOutputProvider,
)

from app.services.structured_output_factory import (
    get_structured_llm_provider,
)

from app.services.clause_extraction_service import (
    ClauseExtractionError,
    ContractNotFoundError as ClauseContractNotFoundError,
    NoChunksFoundError as ClauseNoChunksFoundError,
    ExtractionProviderError,
    extract_clauses_from_chunk,
    extract_contract_clauses,
    list_contract_clauses,
)

from app.services.obligation_extraction_service import (
    ObligationExtractionError,
    ContractNotFoundError as ObligationContractNotFoundError,
    NoClausesFoundError as ObligationNoClausesFoundError,
    ExtractionProviderError as ObligationExtractionProviderError,
    extract_obligations_from_clause,
    extract_contract_obligations,
    list_contract_obligations,
)

__all__ = [
    "create_contract",
    "get_contract",
    "list_contracts",
    "update_contract",
    "delete_contract",
    "associate_contract_file",
    "update_contract_processing_status",
    "VALID_PROCESSING_TRANSITIONS",
    "validate_pdf_upload",
    "save_contract_file",
    "remove_stored_file",
    "sanitize_filename",
    "PDFExtractionError",
    "PDFNotFoundError",
    "PDFPathTraversalError",
    "PDFEncryptedError",
    "PDFCorruptedError",
    "PDFPageLimitExceededError",
    "resolve_pdf_path",
    "extract_text_from_pdf",
    "extract_contract_document",
    "normalize_text",
    "is_noise_text",
    "ChunkingError",
    "ScannedDocumentChunkingError",
    "EmptyDocumentChunkingError",
    "is_heading_line",
    "chunk_page_text",
    "chunk_extraction_result",
    "persist_contract_chunks",
    "list_contract_chunks",
    "EmbeddingProvider",
    "EmbeddingTaskType",
    "EmbeddingError",
    "EmbeddingConfigurationError",
    "EmbeddingValidationError",
    "EmbeddingProviderError",
    "GeminiEmbeddingProvider",
    "get_embedding_provider",
    "EmbeddingGenerationError",
    "ContractNotFoundError",
    "NoChunksFoundError",
    "generate_contract_embeddings",
    "RetrievalError",
    "NoEmbeddedChunksError",
    "query_contract_chunks",
    "KeywordRetrievalError",
    "query_contract_keywords",
    "DEFAULT_RRF_K",
    "HybridRetrievalError",
    "compute_rrf_score",
    "reciprocal_rank_fusion",
    "query_contract_hybrid",
    "StructuredOutputError",
    "StructuredOutputConfigurationError",
    "StructuredOutputProviderError",
    "StructuredOutputParseError",
    "StructuredOutputValidationError",
    "clean_json_text",
    "validate_structured_output",
    "StructuredLLMProvider",
    "GeminiStructuredOutputProvider",
    "get_structured_llm_provider",
    "ClauseExtractionError",
    "ClauseContractNotFoundError",
    "ClauseNoChunksFoundError",
    "ExtractionProviderError",
    "extract_clauses_from_chunk",
    "extract_contract_clauses",
    "list_contract_clauses",
    "ObligationExtractionError",
    "ObligationContractNotFoundError",
    "ObligationNoClausesFoundError",
    "ObligationExtractionProviderError",
    "extract_obligations_from_clause",
    "extract_contract_obligations",
    "list_contract_obligations",
]
